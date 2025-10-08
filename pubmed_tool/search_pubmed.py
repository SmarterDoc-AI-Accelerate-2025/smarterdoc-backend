"""
PubMed Article Search Tool via ORCID
Searches PubMed for articles by doctors from the NPI database using ORCID.

Process:
1. Search ORCID using doctor's name and address
2. Use ORCID to find PubMed articles
"""

import json
import time
import requests
from typing import List, Dict, Any, Optional
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ORCIDSearcher:
    """Search ORCID for researcher profiles"""
    
    BASE_URL = "https://pub.orcid.org/v3.0/search/"
    
    def __init__(self):
        """Initialize ORCID searcher"""
        self.headers = {
            'Accept': 'application/json'
        }
        self.delay = 0.5  # Rate limiting for ORCID API
    
    def search_orcid(
        self, 
        first_name: str, 
        last_name: str, 
        city: str = None, 
        state: str = None,
        use_location: bool = False
    ) -> Optional[str]:
        """
        Search for ORCID ID using name
        
        Args:
            first_name: Researcher's first name
            last_name: Researcher's last name
            city: City name (not used - kept for compatibility)
            state: State name (optional, only used if use_location=True)
            use_location: Whether to include state in search (default: False)
            
        Returns:
            ORCID ID if found, None otherwise
            
        Note:
            By default, only searches by name. Location filtering is disabled
            because city/state names are not organization names and can reduce
            search accuracy.
        """
        # Build search query - primarily use name
        query_parts = [
            f'given-names:{first_name}',
            f'family-name:{last_name}'
        ]
        
        # Optionally add location filter (disabled by default)
        # Only use if explicitly enabled, as it may reduce accuracy
        if use_location and state:
            query_parts.append(f'text:{state}')
        
        query = ' AND '.join(query_parts)
        
        params = {
            'q': query,
            'rows': 1  # Get top result only
        }
        
        try:
            response = requests.get(
                self.BASE_URL,
                params=params,
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            results = data.get('result', [])
            
            if results:
                orcid_identifier = results[0].get('orcid-identifier', {})
                orcid_id = orcid_identifier.get('path')
                
                if orcid_id:
                    logger.info(f"  Found ORCID: {orcid_id}")
                    time.sleep(self.delay)
                    return orcid_id
            
            logger.info("  No ORCID found")
            time.sleep(self.delay)
            return None
            
        except Exception as e:
            logger.error(f"Error searching ORCID for {first_name} {last_name}: {e}")
            time.sleep(self.delay)
            return None


class PubMedSearcher:
    """Search PubMed for articles using ORCID"""
    
    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    
    def __init__(self, email: str = "your_email@example.com", api_key: str = None):
        """
        Initialize PubMed searcher
        
        Args:
            email: Your email (required by NCBI)
            api_key: Optional NCBI API key for higher rate limits
        """
        self.email = email
        self.api_key = api_key
        # Rate limiting: 3 requests/sec without key, 10/sec with key
        self.delay = 0.1 if api_key else 0.34
    
    def search_by_orcid(self, orcid_id: str, max_results: int = 100) -> List[str]:
        """
        Search PubMed for articles by ORCID ID
        
        Args:
            orcid_id: ORCID identifier
            max_results: Maximum number of results to return
            
        Returns:
            List of PubMed article IDs
        """
        # Search using ORCID field in PubMed
        query = f"{orcid_id}[ORCID]"
        
        params = {
            'db': 'pubmed',
            'term': query,
            'retmax': max_results,
            'retmode': 'json',
            'email': self.email
        }
        
        if self.api_key:
            params['api_key'] = self.api_key
        
        try:
            response = requests.get(
                f"{self.BASE_URL}esearch.fcgi",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            pmids = data.get('esearchresult', {}).get('idlist', [])
            
            # Rate limiting
            time.sleep(self.delay)
            
            return pmids
            
        except Exception as e:
            logger.error(f"Error searching PubMed for ORCID {orcid_id}: {e}")
            time.sleep(self.delay)
            return []
    
    def search_by_name_and_specialty(
        self, 
        first_name: str, 
        last_name: str, 
        specialty: str = None, 
        max_results: int = 100
    ) -> List[str]:
        """
        Search PubMed for articles by author name and specialty
        (Fallback method when ORCID is not available or returns no results)
        
        Args:
            first_name: Author's first name
            last_name: Author's last name
            specialty: Medical specialty or taxonomy (e.g., "Cardiologist", "Oncologist")
            max_results: Maximum number of results to return
            
        Returns:
            List of PubMed article IDs
        """
        # Construct author query with specialty
        query_parts = [f"{last_name} {first_name}[Author]"]
        
        # Add specialty/taxonomy as additional search term
        if specialty:
            # Clean up specialty name
            specialty_clean = specialty.strip()
            if specialty_clean and specialty_clean != '--':
                # Add specialty to improve relevance
                query_parts.append(f"{specialty_clean}")
        
        query = " AND ".join(query_parts)
        
        params = {
            'db': 'pubmed',
            'term': query,
            'retmax': max_results,
            'retmode': 'json',
            'email': self.email
        }
        
        if self.api_key:
            params['api_key'] = self.api_key
        
        try:
            response = requests.get(
                f"{self.BASE_URL}esearch.fcgi",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            pmids = data.get('esearchresult', {}).get('idlist', [])
            
            # Rate limiting
            time.sleep(self.delay)
            
            return pmids
            
        except Exception as e:
            logger.error(f"Error searching PubMed for {first_name} {last_name} ({specialty}): {e}")
            time.sleep(self.delay)
            return []
    
    def get_article_links(self, pmids: List[str]) -> List[str]:
        """
        Convert PubMed IDs to article links
        
        Args:
            pmids: List of PubMed IDs
            
        Returns:
            List of article URLs
        """
        return [f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" for pmid in pmids]


def load_doctor_data(file_path: str) -> List[Dict[str, Any]]:
    """Load doctor data from JSON file (specialty_doctors.json format)"""
    logger.info(f"Loading doctor data from {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        # specialty_doctors.json is already a list of doctors
        return data if isinstance(data, list) else data.get('results', [])


def get_doctor_address(doctor: Dict[str, Any]) -> tuple:
    """
    Extract city and state from doctor's address
    
    Args:
        doctor: Doctor data from NPI
        
    Returns:
        Tuple of (city, state)
    """
    addresses = doctor.get('addresses', [])
    if addresses:
        # Prefer LOCATION address, fallback to MAILING
        location_addr = None
        mailing_addr = None
        
        for addr in addresses:
            if addr.get('address_purpose') == 'LOCATION':
                location_addr = addr
                break
            elif addr.get('address_purpose') == 'MAILING':
                mailing_addr = addr
        
        addr = location_addr or mailing_addr
        if addr:
            city = addr.get('city', '').strip()
            state = addr.get('state', '').strip()
            return city, state
    
    return None, None


def get_doctor_taxonomy(doctor: Dict[str, Any]) -> Optional[str]:
    """
    Extract primary taxonomy (medical specialty) from doctor's data
    
    Args:
        doctor: Doctor data from NPI
        
    Returns:
        Primary taxonomy description (e.g., "Cardiologist", "Oncologist")
        or None if not available
    """
    taxonomies = doctor.get('taxonomies', [])
    if taxonomies:
        # Look for primary taxonomy first
        for taxonomy in taxonomies:
            if taxonomy.get('primary'):
                desc = taxonomy.get('desc', '').strip()
                if desc and desc != '--':
                    return desc
        
        # If no primary, use first available
        if taxonomies[0].get('desc'):
            desc = taxonomies[0].get('desc', '').strip()
            if desc and desc != '--':
                return desc
    
    return None


def search_all_doctors(
    doctor_file_path: str,
    output_file_path: str,
    email: str = "your_email@example.com",
    api_key: str = None,
    max_doctors: int = None,
    max_articles_per_doctor: int = 100,
    use_location_filter: bool = False
):
    """
    Search PubMed for all doctors in the specialty database via ORCID
    
    Process:
    1. For each doctor, search ORCID using name (and optionally location)
    2. If ORCID found, search PubMed using ORCID
    3. Save results with ORCID and article links
    
    Args:
        doctor_file_path: Path to specialty doctors JSON file
        output_file_path: Path to save results
        email: Your email for NCBI API
        api_key: Optional NCBI API key
        max_doctors: Maximum number of doctors to process (None for all)
        max_articles_per_doctor: Maximum articles to retrieve per doctor
        use_location_filter: Use state in ORCID search (default: False, name-only search)
    """
    # Load doctor data
    doctors = load_doctor_data(doctor_file_path)
    
    total_doctors = len(doctors)
    if max_doctors:
        doctors = doctors[:max_doctors]
        logger.info(f"Processing first {max_doctors} of {total_doctors} doctors")
    else:
        logger.info(f"Processing all {total_doctors} doctors")
    
    # Initialize searchers
    orcid_searcher = ORCIDSearcher()
    pubmed_searcher = PubMedSearcher(email=email, api_key=api_key)
    
    # Results storage
    results = []
    stats = {
        'total_processed': 0,
        'orcid_found': 0,
        'orcid_not_found': 0,
        'with_articles': 0,
        'total_articles': 0,
        'search_methods': {
            'orcid': 0,
            'orcid_found_but_fallback_to_name': 0,
            'name_and_specialty': 0,
            'no_results': 0
        }
    }
    
    # Process each doctor
    for idx, doctor in enumerate(doctors, 1):
        npi = doctor.get('number', 'Unknown')
        basic_info = doctor.get('basic', {})
        first_name = basic_info.get('first_name', '').strip()
        last_name = basic_info.get('last_name', '').strip()
        
        # Skip if name is missing
        if not first_name or not last_name or first_name == '--' or last_name == '--':
            logger.warning(f"Skipping NPI {npi}: incomplete name")
            continue
        
        # Get address and taxonomy
        city, state = get_doctor_address(doctor)
        taxonomy = get_doctor_taxonomy(doctor)
        
        logger.info(f"[{idx}/{len(doctors)}] Processing: {first_name} {last_name} (NPI: {npi})")
        if use_location_filter:
            logger.info(f"  Location: {city}, {state}")
        if taxonomy:
            logger.info(f"  Specialty: {taxonomy}")
        
        # Step 1: Search for ORCID (by default, only use name)
        orcid_id = orcid_searcher.search_orcid(
            first_name, last_name, city, state, 
            use_location=use_location_filter
        )
        
        # Initialize variables
        pmids = []
        search_method = None
        
        # Step 2: Search PubMed
        if orcid_id:
            stats['orcid_found'] += 1
            logger.info(f"  Found ORCID: {orcid_id}")
            
            # Try searching PubMed using ORCID
            pmids = pubmed_searcher.search_by_orcid(orcid_id, max_results=max_articles_per_doctor)
            
            if pmids:
                search_method = 'orcid'
                logger.info(f"  Found {len(pmids)} articles via ORCID")
            else:
                logger.info(f"  No articles found via ORCID, trying name+specialty fallback...")
                # Fallback: search by name and specialty
                pmids = pubmed_searcher.search_by_name_and_specialty(
                    first_name, last_name, taxonomy, max_results=max_articles_per_doctor
                )
                if pmids:
                    search_method = 'orcid_found_but_fallback_to_name'
                    logger.info(f"  Found {len(pmids)} articles via name+specialty")
                else:
                    search_method = 'orcid_found_but_no_results'
                    logger.info(f"  No articles found")
        else:
            stats['orcid_not_found'] += 1
            logger.info(f"  ORCID not found, trying name+specialty search...")
            
            # Fallback: search by name and specialty
            pmids = pubmed_searcher.search_by_name_and_specialty(
                first_name, last_name, taxonomy, max_results=max_articles_per_doctor
            )
            if pmids:
                search_method = 'name_and_specialty'
                logger.info(f"  Found {len(pmids)} articles via name+specialty")
            else:
                search_method = 'no_results'
                logger.info(f"  No articles found")
        
        # Convert PMIDs to links
        article_links = pubmed_searcher.get_article_links(pmids)
        
        # Update statistics
        if article_links:
            stats['with_articles'] += 1
            stats['total_articles'] += len(article_links)
        
        # Update search method statistics
        if search_method:
            if search_method in stats['search_methods']:
                stats['search_methods'][search_method] += 1
        
        # Initialize result entry
        result_entry = {
            'npi': npi,
            'first_name': first_name,
            'last_name': last_name,
            'credential': basic_info.get('credential', ''),
            'taxonomy': taxonomy,
            'city': city,
            'state': state,
            'orcid': orcid_id,
            'search_method': search_method,
            'article_count': len(article_links),
            'article_links': article_links
        }
        
        results.append(result_entry)
        stats['total_processed'] += 1
        
        # Save progress periodically (every 50 doctors)
        if idx % 50 == 0:
            logger.info(f"Saving progress... ({stats['total_processed']} doctors processed)")
            logger.info(f"  ORCID found: {stats['orcid_found']}, Not found: {stats['orcid_not_found']}")
            logger.info(f"  With articles: {stats['with_articles']}, Total articles: {stats['total_articles']}")
            
            with open(output_file_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'statistics': stats,
                    'doctors': results
                }, f, indent=2, ensure_ascii=False)
    
    # Final save
    logger.info(f"Saving final results to {output_file_path}")
    with open(output_file_path, 'w', encoding='utf-8') as f:
        json.dump({
            'statistics': stats,
            'doctors': results
        }, f, indent=2, ensure_ascii=False)
    
    logger.info("=" * 60)
    logger.info("Search complete!")
    logger.info(f"Total processed: {stats['total_processed']} doctors")
    logger.info(f"ORCID found: {stats['orcid_found']} ({stats['orcid_found']/stats['total_processed']*100:.1f}%)")
    logger.info(f"ORCID not found: {stats['orcid_not_found']}")
    logger.info(f"Doctors with articles: {stats['with_articles']}")
    logger.info(f"Total articles found: {stats['total_articles']}")
    logger.info("")
    logger.info("Search Methods:")
    logger.info(f"  Via ORCID only: {stats['search_methods']['orcid']}")
    logger.info(f"  ORCID found but used fallback: {stats['search_methods']['orcid_found_but_fallback_to_name']}")
    logger.info(f"  Via name+specialty: {stats['search_methods']['name_and_specialty']}")
    logger.info(f"  No results: {stats['search_methods']['no_results']}")
    logger.info("=" * 60)


if __name__ == "__main__":
    # Configuration
    DOCTOR_FILE = "specialty_doctors.json"
    OUTPUT_FILE = "pubmed_articles_results.json"
    
    # IMPORTANT: Replace with your email (required by NCBI)
    EMAIL = "your_email@example.com"
    
    # Optional: Add your NCBI API key for higher rate limits
    # Get one at: https://www.ncbi.nlm.nih.gov/account/settings/
    API_KEY = None  
    
    # Limit for testing - set to None to process all doctors
    # WARNING: Processing all doctors will take a LONG time!
    MAX_DOCTORS = 10000  # Start with 10 doctors for testing
    
    # Location filter - use state in ORCID search (default: False for better accuracy)
    # Set to True to include state information in ORCID search
    USE_LOCATION_FILTER = False
    
    print("=" * 60)
    print("PubMed Article Search Tool via ORCID")
    print("=" * 60)
    print(f"Doctor Data File: {DOCTOR_FILE}")
    print(f"Output File: {OUTPUT_FILE}")
    print(f"Max Doctors: {MAX_DOCTORS if MAX_DOCTORS else 'ALL'}")
    print(f"Location Filter: {'Enabled' if USE_LOCATION_FILTER else 'Disabled (name-only search)'}")
    print()
    print("Search Strategy (with fallback):")
    print("  1. Search ORCID using name" + (" + state" if USE_LOCATION_FILTER else " only"))
    print("  2. Search PubMed using ORCID")
    print("  3. If no ORCID or no results → Fallback: Search by name + specialty")
    print("  4. If still no results → Return empty")
    print("=" * 60)
    
    # Run the search
    search_all_doctors(
        doctor_file_path=DOCTOR_FILE,
        output_file_path=OUTPUT_FILE,
        email=EMAIL,
        api_key=API_KEY,
        max_doctors=MAX_DOCTORS,
        max_articles_per_doctor=100,
        use_location_filter=USE_LOCATION_FILTER
    )

