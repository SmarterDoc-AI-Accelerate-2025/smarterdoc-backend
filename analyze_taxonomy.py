#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyze taxonomy distribution in NPI data
"""

import json
from collections import Counter

def analyze_taxonomy(file_path):
    """Analyze taxonomy distribution in JSON file"""
    print(f"Analyzing file: {file_path}")
    
    # Read JSON file
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"Total records: {data['result_count']}")
    
    # Collect all unique taxonomies
    taxonomy_set = set()
    taxonomy_codes = set()
    taxonomy_count = Counter()
    
    for record in data['results']:
        taxonomies = record.get('taxonomies', []) or []
        for tax in taxonomies:
            desc = tax.get('desc', '') or tax.get('taxonomy_description', '')
            code = tax.get('code', '')
            if desc:
                taxonomy_set.add(desc)
                taxonomy_count[desc] += 1
            if code:
                taxonomy_codes.add(code)
    
    print(f"Unique specialty descriptions: {len(taxonomy_set)}")
    print(f"Unique specialty codes: {len(taxonomy_codes)}")
    
    # Show top 20 most common specialties
    print(f"\nTop 20 most common specialties:")
    for i, (desc, count) in enumerate(taxonomy_count.most_common(20), 1):
        print(f"{i:2d}. {desc}: {count}")
    
    # Show all specialty list
    print(f"\nAll specialties (alphabetically sorted):")
    for i, desc in enumerate(sorted(taxonomy_set), 1):
        count = taxonomy_count[desc]
        print(f"{i:3d}. {desc}: {count}")
    
    return taxonomy_set, taxonomy_codes, taxonomy_count

if __name__ == "__main__":
    # Analyze New York data
    print("=" * 60)
    print("Analyzing New York City NPI Data")
    print("=" * 60)
    taxonomy_set, taxonomy_codes, taxonomy_count = analyze_taxonomy('npi_doctors_NewYork_NY_multilevel.json')
    
    print(f"\n" + "=" * 60)
    print("Analyzing Hoboken NPI Data")
    print("=" * 60)
    try:
        analyze_taxonomy('npi_doctors_Hoboken_NJ_unlimited.json')
    except FileNotFoundError:
        print("Hoboken data file not found")
