#!/usr/bin/env python3
"""
Geocode All Doctors with NY Address Priority

This script:
1. Gets all doctors from curated.doctor_profiles
2. Fetches their addresses from raw data
3. Prioritizes NY addresses for geocoding
4. Updates coordinates for all doctors
"""

import os
import time
import json
import random
from typing import List, Dict, Optional, Tuple
import requests
from google.cloud import bigquery
from google.cloud.bigquery import ScalarQueryParameter

# Add the project root to Python path
if 'PYTHONPATH' not in os.environ or '.' not in os.environ['PYTHONPATH']:
    os.environ['PYTHONPATH'] = os.environ.get('PYTHONPATH', '') + (
        ':' if os.environ.get('PYTHONPATH') else '') + '.'

from app.config import settings
from app.deps import get_bq_sync
from app.util.logging import logger


class AllDoctorsGeocoder:
    def __init__(self):
        self.client = get_bq_sync()
        
        # Try to get project ID from settings, then from client, then from environment
        self.project_id = (settings.GCP_PROJECT_ID or 
                          getattr(self.client, 'project', None) or 
                          os.getenv('GOOGLE_CLOUD_PROJECT'))
        
        self.api_key = settings.MAPS_API_KEY
        
        if not self.project_id:
            raise ValueError("GCP_PROJECT_ID must be set in config.py or GOOGLE_CLOUD_PROJECT environment variable")
        if not self.api_key:
            raise ValueError("MAPS_API_KEY must be set in config.py")
        
        # Rate limiting
        self.qps = float(os.getenv("QPS", "6"))  # Queries per second
        self.min_interval = 1.0 / max(self.qps, 0.1)
        self.last_request_time = 0.0
        
        # Batch processing
        self.batch_size = int(os.getenv("BATCH_SIZE", "20"))
        self.max_retries = int(os.getenv("MAX_RETRIES", "3"))
        
        logger.info(f"Initialized geocoder with QPS={self.qps}, batch_size={self.batch_size}")

    def rate_limit(self):
        """Apply rate limiting to respect API quotas."""
        now = time.time()
        sleep_for = self.last_request_time + self.min_interval - now
        if sleep_for > 0:
            time.sleep(sleep_for)
        self.last_request_time = time.time()

    def geocode_address(self, address_components: Dict) -> Optional[Tuple[float, float]]:
        """
        Geocode a single address using Google Maps API.
        """
        # Build full address string
        address_parts = []
        
        if address_components.get('address_1'):
            address_parts.append(address_components['address_1'])
        if address_components.get('address_2'):
            address_parts.append(address_components['address_2'])
        if address_components.get('city'):
            address_parts.append(address_components['city'])
        if address_components.get('state'):
            address_parts.append(address_components['state'])
        if address_components.get('postal_code'):
            address_parts.append(address_components['postal_code'])
        if address_components.get('country_code'):
            address_parts.append(address_components['country_code'])
        
        full_address = ', '.join(filter(None, address_parts))
        
        if not full_address.strip():
            logger.warning("Empty address provided")
            return None
        
        # Apply rate limiting
        self.rate_limit()
        
        # Call Google Maps Geocoding API
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "address": full_address,
            "key": self.api_key
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            status = data.get("status")
            
            if status == "OK" and data.get("results"):
                location = data["results"][0]["geometry"]["location"]
                lat = float(location["lat"])
                lng = float(location["lng"])
                logger.debug(f"Geocoded '{full_address}' -> ({lat}, {lng})")
                return (lat, lng)
            
            elif status == "ZERO_RESULTS":
                logger.warning(f"No results for address: {full_address}")
                return None
            
            elif status in ("OVER_QUERY_LIMIT", "RESOURCE_EXHAUSTED"):
                logger.warning(f"Rate limit exceeded for address: {full_address}")
                time.sleep(2 + random.random())
                return None
            
            else:
                logger.error(f"Geocoding failed for '{full_address}': {status}")
                return None
                
        except Exception as e:
            logger.error(f"Error geocoding address '{full_address}': {e}")
            return None

    def get_all_doctors(self) -> List[Dict]:
        """Get all doctors from the curated table."""
        query = f"""
        SELECT 
            npi,
            first_name,
            last_name,
            latitude,
            longitude
        FROM `{self.project_id}.curated.doctor_profiles`
        ORDER BY npi
        """
        
        result = list(self.client.query(query))
        doctors = []
        
        for row in result:
            doctors.append({
                'npi': row.npi,
                'first_name': row.first_name,
                'last_name': row.last_name,
                'current_latitude': row.latitude,
                'current_longitude': row.longitude
            })
        
        logger.info(f"Found {len(doctors)} doctors in curated table")
        return doctors

    def get_doctor_addresses_from_raw(self, npi: str) -> List[Dict]:
        """Get address data from raw dataset for a specific NPI."""
        query = f"""
        SELECT 
            JSON_EXTRACT_SCALAR(_data, '$.number') AS npi,
            JSON_EXTRACT(_data, '$.addresses') AS addresses
        FROM `{self.project_id}.gcs_npi_staging.npi_doctors_row`
        WHERE JSON_EXTRACT_SCALAR(_data, '$.number') = @npi
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter("npi", "STRING", str(npi))
            ]
        )
        
        result = list(self.client.query(query, job_config=job_config))
        
        if result:
            row = result[0]
            if row.addresses:
                try:
                    if isinstance(row.addresses, list):
                        return row.addresses
                    else:
                        return json.loads(row.addresses)
                except (json.JSONDecodeError, TypeError):
                    return []
        
        return []

    def prioritize_ny_addresses(self, addresses: List[Dict]) -> List[Dict]:
        """
        Prioritize addresses: NY addresses first, then by purpose (LOCATION > MAILING).
        """
        def address_priority(addr):
            # Priority 1: NY addresses
            is_ny = addr.get('state', '').upper() == 'NY'
            # Priority 2: LOCATION over MAILING
            is_location = addr.get('address_purpose', '').upper() == 'LOCATION'
            
            return (not is_ny, not is_location)  # False values sort first
        
        return sorted(addresses, key=address_priority)

    def process_doctor_addresses(self, doctor: Dict) -> Optional[Tuple[float, float, str]]:
        """
        Process a single doctor's addresses with NY priority.
        Returns (latitude, longitude, address_used) or None.
        """
        addresses = self.get_doctor_addresses_from_raw(doctor['npi'])
        if not addresses:
            logger.warning(f"No addresses found for NPI {doctor['npi']}")
            return None
        
        # Prioritize NY addresses
        sorted_addresses = self.prioritize_ny_addresses(addresses)
        
        logger.info(f"Processing NPI {doctor['npi']} ({doctor['first_name']} {doctor['last_name']})")
        logger.info(f"Found {len(sorted_addresses)} addresses, prioritizing NY addresses")
        
        for i, address in enumerate(sorted_addresses):
            state = address.get('state', '').upper()
            purpose = address.get('address_purpose', '').upper()
            is_ny = state == 'NY'
            
            logger.info(f"  Address {i+1} ({purpose}, {state}): {address.get('address_1', '')} {address.get('city', '')}")
            
            coords = self.geocode_address(address)
            if coords:
                lat, lng = coords
                address_used = f"{address.get('address_1', '')}, {address.get('city', '')}, {state}"
                logger.info(f"  ✅ Successfully geocoded NY={is_ny} address: {address_used}")
                return (lat, lng, address_used)
            else:
                logger.warning(f"  ❌ Failed to geocode address {i+1}")
        
        logger.warning(f"Failed to geocode any address for NPI {doctor['npi']}")
        return None

    def update_doctor_coordinates(self, npi: str, latitude: float, longitude: float, address_used: str = None) -> bool:
        """Update doctor coordinates and address in the curated table."""
        query = f"""
        UPDATE `{self.project_id}.curated.doctor_profiles`
        SET 
            latitude = @latitude,
            longitude = @longitude,
            address = @address,
            updated_at = CURRENT_TIMESTAMP()
        WHERE CAST(npi AS STRING) = @npi
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter("latitude", "FLOAT64", latitude),
                ScalarQueryParameter("longitude", "FLOAT64", longitude),
                ScalarQueryParameter("address", "STRING", address_used or ""),
                ScalarQueryParameter("npi", "STRING", str(npi))
            ]
        )
        
        try:
            job = self.client.query(query, job_config=job_config)
            job.result()  # Wait for completion
            logger.info(f"Updated coordinates and address for NPI {npi}: ({latitude}, {longitude}) - {address_used}")
            return True
        except Exception as e:
            logger.error(f"Failed to update coordinates and address for NPI {npi}: {e}")
            return False

    def process_batch(self, doctors: List[Dict]) -> Dict[str, int]:
        """Process a batch of doctors and return statistics."""
        stats = {
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'ny_addresses': 0,
            'non_ny_addresses': 0
        }
        
        for doctor in doctors:
            try:
                stats['processed'] += 1
                
                # Try to geocode the doctor's address
                result = self.process_doctor_addresses(doctor)
                
                if result:
                    latitude, longitude, address_used = result
                    
                    # Check if NY address was used
                    if 'NY' in address_used.upper():
                        stats['ny_addresses'] += 1
                    else:
                        stats['non_ny_addresses'] += 1
                    
                    success = self.update_doctor_coordinates(
                        doctor['npi'], latitude, longitude, address_used
                    )
                    
                    if success:
                        stats['successful'] += 1
                    else:
                        stats['failed'] += 1
                else:
                    stats['failed'] += 1
                    
            except Exception as e:
                logger.error(f"Error processing doctor {doctor.get('npi', 'unknown')}: {e}")
                stats['failed'] += 1
        
        return stats

    def run_geocoding_job(self, max_doctors: int = None):
        """Main function to run the geocoding job."""
        logger.info("🚀 Starting All Doctors Geocoding Job (NY Priority)")
        logger.info("=" * 60)
        
        # Get all doctors
        doctors = self.get_all_doctors()
        
        if max_doctors:
            doctors = doctors[:max_doctors]
            logger.info(f"Limiting to first {max_doctors} doctors")
        
        logger.info(f"📍 Processing {len(doctors)} doctors...")
        
        # Process in batches
        total_stats = {
            'processed': 0, 
            'successful': 0, 
            'failed': 0, 
            'ny_addresses': 0, 
            'non_ny_addresses': 0
        }
        
        for i in range(0, len(doctors), self.batch_size):
            batch = doctors[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (len(doctors) + self.batch_size - 1) // self.batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} doctors)")
            
            batch_stats = self.process_batch(batch)
            
            # Update totals
            for key in total_stats:
                total_stats[key] += batch_stats[key]
            
            # Progress update
            logger.info(f"Batch {batch_num} completed: {batch_stats}")
            
            # Small delay between batches
            if i + self.batch_size < len(doctors):
                time.sleep(2)
        
        # Final summary
        logger.info("🎉 Geocoding Job Completed!")
        logger.info("=" * 60)
        logger.info(f"📊 Final Statistics:")
        logger.info(f"   Total Processed: {total_stats['processed']}")
        logger.info(f"   Successful: {total_stats['successful']}")
        logger.info(f"   Failed: {total_stats['failed']}")
        logger.info(f"   NY Addresses Used: {total_stats['ny_addresses']}")
        logger.info(f"   Non-NY Addresses Used: {total_stats['non_ny_addresses']}")
        
        success_rate = (total_stats['successful'] / total_stats['processed'] * 100) if total_stats['processed'] > 0 else 0
        ny_rate = (total_stats['ny_addresses'] / total_stats['successful'] * 100) if total_stats['successful'] > 0 else 0
        
        logger.info(f"   Success Rate: {success_rate:.1f}%")
        logger.info(f"   NY Address Rate: {ny_rate:.1f}%")


def main():
    """Main function."""
    try:
        geocoder = AllDoctorsGeocoder()
        
        # Get max doctors from command line or use default
        import sys
        max_doctors = int(sys.argv[1]) if len(sys.argv) > 1 else None
        
        geocoder.run_geocoding_job(max_doctors=max_doctors)
        
    except Exception as e:
        logger.error(f"❌ Geocoding job failed: {e}")
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
