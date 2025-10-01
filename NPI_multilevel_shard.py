#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NPI Data Extraction Tool - Multi-level Sharding Version
Solves the issue of single specialty exceeding 1200 records
Strategy: Specialty sharding + ZIP code subdivision (when specialty reaches 1200 limit)
"""

import json
import time
import sys
import requests
from typing import Dict, Any, List, Set

# ====== Configuration ======
CITY = "New York"
STATE = "NY"
ADDRESS_PURPOSE = "location"
ENUMERATION_TYPE = "NPI-1"
API_VERSION = "2.1"
PAGE_LIMIT = 200
REQUEST_TIMEOUT = 30
MAX_RETRIES = 5
RETRY_BACKOFF = 2.0
OUTPUT_FILE = None
# ====================


def build_params(city: str, state: str, skip: int, **kwargs) -> Dict[str, str]:
    """Build API request parameters"""
    params = {
        "version": API_VERSION,
        "city": city,
        "state": state,
        "enumeration_type": ENUMERATION_TYPE,
        "address_purpose": ADDRESS_PURPOSE,
        "limit": str(PAGE_LIMIT),
        "skip": str(skip),
    }
    
    # Add filter parameters
    if kwargs.get("taxonomy_description"):
        params["taxonomy_description"] = kwargs["taxonomy_description"]
    if kwargs.get("taxonomy_code"):
        params["taxonomy"] = kwargs["taxonomy_code"]
    if kwargs.get("postal_code"):
        params["postal_code"] = kwargs["postal_code"]
    
    return params


def request_with_retries(url: str, params: Dict[str, str]) -> Dict[str, Any]:
    """HTTP request with retry mechanism"""
    last_err = None
    for i in range(MAX_RETRIES):
        try:
            r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
            time.sleep(RETRY_BACKOFF ** i)
    raise RuntimeError(f"Request failed (retried {MAX_RETRIES} times): {last_err}")


def fetch_single_query(city: str, state: str, **query_params) -> List[Dict[str, Any]]:
    """Fetch all data for a single query (max 1200 records)"""
    base = "https://npiregistry.cms.hhs.gov/api/"
    all_records: List[Dict[str, Any]] = []
    seen_npi: Set[str] = set()
    skip = 0
    consecutive_empty = 0
    MAX_CONSECUTIVE_EMPTY = 3
    MAX_SKIP = 1200
    
    while skip < MAX_SKIP:
        params = build_params(city, state, skip, **query_params)
        data = request_with_retries(base, params)
        batch = data.get("results", []) or []
        
        added = 0
        for rec in batch:
            npi = rec.get("number")
            if npi and npi not in seen_npi:
                all_records.append(rec)
                seen_npi.add(npi)
                added += 1
        
        # Check if should continue
        if len(batch) == 0 or added == 0:
            consecutive_empty += 1
            if consecutive_empty >= MAX_CONSECUTIVE_EMPTY:
                break
        else:
            consecutive_empty = 0
        
        if len(batch) < PAGE_LIMIT:
            break
        
        skip += PAGE_LIMIT
        time.sleep(0.3)  # Avoid triggering API limits
    
    return all_records


def get_postal_codes_for_taxonomy(city: str, state: str, taxonomy_desc: str) -> List[str]:
    """Get all postal codes for a specific specialty"""
    base = "https://npiregistry.cms.hhs.gov/api/"
    params = {
        "version": API_VERSION,
        "city": city,
        "state": state,
        "enumeration_type": ENUMERATION_TYPE,
        "address_purpose": ADDRESS_PURPOSE,
        "taxonomy_description": taxonomy_desc,
        "limit": "200",
        "skip": "0",
    }
    
    try:
        data = request_with_retries(base, params)
        results = data.get("results", []) or []
        
        postal_set = set()
        for rec in results:
            addresses = rec.get("addresses", []) or []
            for addr in addresses:
                if addr.get("address_purpose", "").upper() == "LOCATION":
                    postal = addr.get("postal_code", "")
                    if postal:
                        postal_set.add(postal[:5])
        
        postal_list = sorted(list(postal_set))
        return postal_list
        
    except Exception as e:
        print(f"  [Warning] Failed to get postal codes: {e}")
        return []


def fetch_taxonomy_with_subdivision(city: str, state: str, taxonomy: str,
                                    global_seen_npi: Set[str]) -> List[Dict[str, Any]]:
    """
    Fetch data for a single specialty, subdivide by postal code if reaches 1200 limit
    """
    all_records: List[Dict[str, Any]] = []
    
    display_name = f"{taxonomy[:60]}..." if len(taxonomy) > 60 else taxonomy
    print(f"  [Query] {display_name}", end=" ... ")
    
    # Try direct fetch by specialty description
    records = fetch_single_query(city, state, taxonomy_description=taxonomy)
    
    # If reaches 1200, there may be more data, need to subdivide by postal code
    if len(records) >= 1200:
        print(f"[Reached 1200 limit, subdividing by postal code]")
        
        # Get all postal codes for this specialty
        postal_codes = get_postal_codes_for_taxonomy(city, state, taxonomy)
        
        if postal_codes:
            print(f"    [Info] Found {len(postal_codes)} postal codes, querying each...")
            
            for postal in postal_codes:
                print(f"      [Postal] {postal}", end=" ... ")
                postal_records = fetch_single_query(
                    city, state,
                    taxonomy_description=taxonomy,
                    postal_code=postal
                )
                
                # Deduplicate and add to results
                added = 0
                for rec in postal_records:
                    npi = rec.get("number")
                    if npi and npi not in global_seen_npi:
                        all_records.append(rec)
                        global_seen_npi.add(npi)
                        added += 1
                
                print(f"{added} new records")
                time.sleep(0.3)  # Avoid triggering API limits
        else:
            print(f"    [Warning] Failed to get postal codes, using original 1200 records")
            # Deduplicate and add
            for rec in records:
                npi = rec.get("number")
                if npi and npi not in global_seen_npi:
                    all_records.append(rec)
                    global_seen_npi.add(npi)
    else:
        print(f"{len(records)} records")
        # Deduplicate and add
        for rec in records:
            npi = rec.get("number")
            if npi and npi not in global_seen_npi:
                all_records.append(rec)
                global_seen_npi.add(npi)
    
    return all_records


def get_all_postal_codes(city: str, state: str) -> List[str]:
    """Get all postal codes (traverse first 1200 records)"""
    print(f"\n[Step 1] Fetching all postal codes for {city}, {state}...")
    
    base = "https://npiregistry.cms.hhs.gov/api/"
    postal_set = set()
    skip = 0
    MAX_SKIP = 1200
    
    while skip < MAX_SKIP:
        params = {
            "version": API_VERSION,
            "city": city,
            "state": state,
            "enumeration_type": ENUMERATION_TYPE,
            "address_purpose": ADDRESS_PURPOSE,
            "limit": "200",
            "skip": str(skip),
        }
        
        try:
            data = request_with_retries(base, params)
            results = data.get("results", []) or []
            
            if not results:
                break
            
            for rec in results:
                addresses = rec.get("addresses", []) or []
                for addr in addresses:
                    if addr.get("address_purpose", "").upper() == "LOCATION":
                        postal = addr.get("postal_code", "")
                        if postal:
                            postal_set.add(postal[:5])  # Only take first 5 digits
            
            if len(results) < 200:
                break
            
            skip += 200
            time.sleep(0.2)
            
        except Exception as e:
            print(f"[Warning] Failed to get postal codes at skip={skip}: {e}")
            break
    
    postal_list = sorted(list(postal_set))
    print(f"[Info] Found {len(postal_list)} unique postal codes\n")
    return postal_list


def get_all_taxonomies(city: str, state: str, postal_codes: List[str]) -> List[str]:
    """Collect complete specialty list from all postal codes (using description)"""
    print(f"[Step 2] Collecting specialty list from all postal codes...")
    
    base = "https://npiregistry.cms.hhs.gov/api/"
    taxonomy_set = set()
    
    # Collect specialties from first 200 records of each postal code
    for i, postal in enumerate(postal_codes, 1):
        print(f"  [Postal {i}/{len(postal_codes)}] {postal}", end=" ... ")
        
        params = {
            "version": API_VERSION,
            "city": city,
            "state": state,
            "enumeration_type": ENUMERATION_TYPE,
            "address_purpose": ADDRESS_PURPOSE,
            "postal_code": postal,
            "limit": "200",
            "skip": "0",
        }
        
        try:
            data = request_with_retries(base, params)
            results = data.get("results", []) or []
            
            count_before = len(taxonomy_set)
            for rec in results:
                taxonomies = rec.get("taxonomies", []) or []
                for tax in taxonomies:
                    desc = tax.get("desc", "") or tax.get("taxonomy_description", "")
                    if desc:
                        taxonomy_set.add(desc)
            
            new_count = len(taxonomy_set) - count_before
            print(f"{len(results)} records, {new_count} new specialties, total {len(taxonomy_set)}")
            time.sleep(0.2)
            
        except Exception as e:
            print(f"Failed: {e}")
    
    taxonomy_list = sorted(list(taxonomy_set))
    print(f"\n[Info] Total found {len(taxonomy_list)} unique specialties\n")
    return taxonomy_list


def fetch_all_multilevel(city: str, state: str) -> List[Dict[str, Any]]:
    """Fetch all data using multi-level sharding strategy"""
    all_records: List[Dict[str, Any]] = []
    global_seen_npi: Set[str] = set()
    
    print(f"\n{'='*70}")
    print(f"Starting multi-level sharding query")
    print(f"Target: {city}, {state}")
    print(f"Strategy: Postal collection → Specialty discovery → Specialty sharding → Postal subdivision on limit")
    print(f"{'='*70}\n")
    
    # Step 1: Get all postal codes
    postal_codes = get_all_postal_codes(city, state)
    
    if not postal_codes:
        print("[Error] Failed to get postal code list")
        return []
    
    # Step 2: Collect complete specialty list from all postal codes
    taxonomies = get_all_taxonomies(city, state, postal_codes)
    
    if not taxonomies:
        print("[Error] Failed to get specialty list")
        return []
    
    # Step 3: Query each specialty (subdivide by postal code if necessary)
    print(f"[Step 3] Starting specialty data query...\n")
    for i, taxonomy in enumerate(taxonomies, 1):
        print(f"[{i}/{len(taxonomies)}]", end=" ")
        
        records = fetch_taxonomy_with_subdivision(
            city, state, 
            taxonomy,
            global_seen_npi
        )
        all_records.extend(records)
        
        print(f"    [Cumulative] {len(all_records)} records")
    
    print(f"\n{'='*70}")
    print(f"Query completed!")
    print(f"Total unique NPIs: {len(all_records)} records")
    print(f"{'='*70}\n")
    
    return all_records


def write_json(records: List[Dict[str, Any]], filepath: str) -> None:
    """Write JSON file"""
    output_data = {
        "result_count": len(records),
        "results": records
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)


def sanitize_filename(s: str) -> str:
    """Sanitize filename"""
    return "".join(c for c in s if c.isalnum() or c in ("-", "_")).strip("_") or "x"


def main():
    city = CITY
    state = STATE
    
    # Support command line arguments
    if len(sys.argv) >= 3:
        city = sys.argv[1]
        state = sys.argv[2]
    
    # Execute query
    records = fetch_all_multilevel(city, state)
    
    # Generate output filename
    if OUTPUT_FILE:
        out = OUTPUT_FILE
    else:
        out = f"npi_doctors_{sanitize_filename(city)}_{sanitize_filename(state)}_multilevel.json"
    
    write_json(records, out)
    print(f"[Complete] Saved {len(records)} records to {out}")


if __name__ == "__main__":
    main()
