#!/usr/bin/env python3
"""
BigQuery Doctor Profiles Table Backup Script

This script creates a backup of the curated.doctor_profiles table before any modifications.
The backup includes both schema and data.
"""

import os
import sys
from datetime import datetime
from typing import Optional
from google.cloud import bigquery
from google.cloud.bigquery import CopyJobConfig

# Add the project root to Python path
if 'PYTHONPATH' not in os.environ or '.' not in os.environ['PYTHONPATH']:
    os.environ['PYTHONPATH'] = os.environ.get('PYTHONPATH', '') + (
        ':' if os.environ.get('PYTHONPATH') else '') + '.'

from app.config import settings
from app.deps import get_bq_sync
from app.util.logging import logger


def get_table_info(client: bigquery.Client, table_id: str) -> dict:
    """Get information about the current table."""
    try:
        table = client.get_table(table_id)
        
        # Get row count
        count_query = f"SELECT COUNT(*) as row_count FROM `{table_id}`"
        count_result = list(client.query(count_query))[0]
        row_count = count_result.row_count
        
        return {
            'exists': True,
            'row_count': row_count,
            'schema_fields': len(table.schema),
            'size_bytes': table.num_bytes,
            'created': table.created,
            'modified': table.modified,
            'location': table.location
        }
    except Exception as e:
        logger.error(f"Error getting table info: {e}")
        return {'exists': False, 'error': str(e)}


def create_backup_table(client: bigquery.Client, 
                       source_table_id: str, 
                       backup_table_id: str) -> bool:
    """
    Create a backup of the source table by copying it.
    This preserves both schema and data.
    """
    try:
        logger.info(f"Creating backup: {source_table_id} -> {backup_table_id}")
        
        # Configure the copy job
        copy_config = CopyJobConfig(
            write_disposition="WRITE_TRUNCATE",  # Overwrite if exists
            create_disposition="CREATE_IF_NEEDED"
        )
        
        # Start the copy job
        copy_job = client.copy_table(
            source_table_id, 
            backup_table_id, 
            job_config=copy_config
        )
        
        # Wait for completion
        copy_job.result()
        
        logger.info(f"✅ Backup completed successfully: {backup_table_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Backup failed: {e}")
        return False


def verify_backup(client: bigquery.Client, 
                  source_table_id: str, 
                  backup_table_id: str) -> bool:
    """Verify that the backup was created successfully."""
    try:
        # Get source table info
        source_info = get_table_info(client, source_table_id)
        backup_info = get_table_info(client, backup_table_id)
        
        if not source_info['exists'] or not backup_info['exists']:
            logger.error("Source or backup table doesn't exist")
            return False
            
        # Compare row counts
        if source_info['row_count'] != backup_info['row_count']:
            logger.error(f"Row count mismatch: source={source_info['row_count']}, backup={backup_info['row_count']}")
            return False
            
        logger.info(f"✅ Backup verification successful:")
        logger.info(f"   Source rows: {source_info['row_count']}")
        logger.info(f"   Backup rows: {backup_info['row_count']}")
        logger.info(f"   Schema fields: {backup_info['schema_fields']}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Backup verification failed: {e}")
        return False


def main():
    """Main backup function."""
    print("🔄 Starting Doctor Profiles Table Backup")
    print("=" * 50)
    
    # Initialize BigQuery client
    try:
        client = get_bq_sync()
        logger.info("✅ BigQuery client initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize BigQuery client: {e}")
        return False
    
    # Define table IDs
    project_id = settings.GCP_PROJECT_ID or os.getenv("GOOGLE_CLOUD_PROJECT")
    dataset_id = settings.BQ_CURATED_DATASET
    table_name = settings.BQ_PROFILES_TABLE
    
    if not project_id:
        logger.error("❌ GCP_PROJECT_ID not set. Please set GOOGLE_CLOUD_PROJECT environment variable.")
        return False
    
    source_table_id = f"{project_id}.{dataset_id}.{table_name}"
    
    # Create backup table name with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_table_name = f"{table_name}_backup_{timestamp}"
    backup_table_id = f"{project_id}.{dataset_id}.{backup_table_name}"
    
    print(f"📊 Source Table: {source_table_id}")
    print(f"💾 Backup Table: {backup_table_id}")
    print()
    
    # Check source table info
    print("🔍 Checking source table...")
    source_info = get_table_info(client, source_table_id)
    
    if not source_info['exists']:
        logger.error(f"❌ Source table does not exist: {source_table_id}")
        return False
        
    print(f"✅ Source table found:")
    print(f"   Rows: {source_info['row_count']:,}")
    print(f"   Schema fields: {source_info['schema_fields']}")
    print(f"   Size: {source_info['size_bytes']:,} bytes")
    print(f"   Created: {source_info['created']}")
    print(f"   Modified: {source_info['modified']}")
    print()
    
    # Create backup
    print("📋 Creating backup...")
    backup_success = create_backup_table(client, source_table_id, backup_table_id)
    
    if not backup_success:
        logger.error("❌ Backup creation failed")
        return False
    
    # Verify backup
    print("🔍 Verifying backup...")
    verification_success = verify_backup(client, source_table_id, backup_table_id)
    
    if not verification_success:
        logger.error("❌ Backup verification failed")
        return False
    
    print()
    print("🎉 BACKUP COMPLETED SUCCESSFULLY!")
    print("=" * 50)
    print(f"✅ Source: {source_table_id}")
    print(f"✅ Backup: {backup_table_id}")
    print(f"✅ Rows: {source_info['row_count']:,}")
    print(f"✅ Timestamp: {timestamp}")
    print()
    print("💡 You can now safely modify the original table.")
    print("💡 To restore from backup, use:")
    print(f"   python -m jobs.restore_doctor_profiles {backup_table_name}")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
