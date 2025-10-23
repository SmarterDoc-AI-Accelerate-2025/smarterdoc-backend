#!/usr/bin/env python3
"""
BigQuery Doctor Profiles Table Restore Script

This script restores the curated.doctor_profiles table from a backup.
Usage: python -m jobs.restore_doctor_profiles <backup_table_name>
"""

import os
import sys
import argparse
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


def list_available_backups(client: bigquery.Client) -> list:
    """List all available backup tables."""
    try:
        project_id = settings.GCP_PROJECT_ID
        dataset_id = settings.BQ_CURATED_DATASET
        
        # Query to find backup tables
        query = f"""
        SELECT table_name, created, row_count
        FROM `{project_id}.{dataset_id}.INFORMATION_SCHEMA.TABLES`
        WHERE table_name LIKE '{settings.BQ_PROFILES_TABLE}_backup_%'
        ORDER BY created DESC
        """
        
        results = list(client.query(query))
        return [dict(row) for row in results]
        
    except Exception as e:
        logger.error(f"Error listing backups: {e}")
        return []


def get_table_info(client: bigquery.Client, table_id: str) -> dict:
    """Get information about a table."""
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
            'modified': table.modified
        }
    except Exception as e:
        return {'exists': False, 'error': str(e)}


def restore_from_backup(client: bigquery.Client, 
                       backup_table_id: str, 
                       target_table_id: str,
                       confirm: bool = False) -> bool:
    """
    Restore the target table from backup.
    """
    try:
        if not confirm:
            logger.error("❌ Restore operation requires confirmation. Use --confirm flag.")
            return False
            
        logger.info(f"🔄 Restoring from backup: {backup_table_id} -> {target_table_id}")
        
        # Configure the copy job
        copy_config = CopyJobConfig(
            write_disposition="WRITE_TRUNCATE",  # Overwrite target table
            create_disposition="CREATE_IF_NEEDED"
        )
        
        # Start the copy job
        copy_job = client.copy_table(
            backup_table_id, 
            target_table_id, 
            job_config=copy_config
        )
        
        # Wait for completion
        copy_job.result()
        
        logger.info(f"✅ Restore completed successfully: {target_table_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Restore failed: {e}")
        return False


def main():
    """Main restore function."""
    parser = argparse.ArgumentParser(description='Restore doctor profiles table from backup')
    parser.add_argument('backup_name', nargs='?', help='Backup table name (without dataset prefix)')
    parser.add_argument('--list', action='store_true', help='List available backups')
    parser.add_argument('--confirm', action='store_true', help='Confirm the restore operation')
    
    args = parser.parse_args()
    
    print("🔄 Doctor Profiles Table Restore")
    print("=" * 50)
    
    # Initialize BigQuery client
    try:
        client = get_bq_sync()
        logger.info("✅ BigQuery client initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize BigQuery client: {e}")
        return False
    
    # Define table IDs
    project_id = settings.GCP_PROJECT_ID
    dataset_id = settings.BQ_CURATED_DATASET
    table_name = settings.BQ_PROFILES_TABLE
    
    target_table_id = f"{project_id}.{dataset_id}.{table_name}"
    
    # List available backups if requested
    if args.list or not args.backup_name:
        print("📋 Available backups:")
        backups = list_available_backups(client)
        
        if not backups:
            print("   No backup tables found.")
            return True
            
        for i, backup in enumerate(backups, 1):
            print(f"   {i}. {backup['table_name']}")
            print(f"      Created: {backup['created']}")
            print(f"      Rows: {backup['row_count']:,}")
            print()
        
        if not args.backup_name:
            print("💡 Usage: python -m jobs.restore_doctor_profiles <backup_table_name> --confirm")
            return True
    
    # Validate backup table
    backup_table_id = f"{project_id}.{dataset_id}.{args.backup_name}"
    
    print(f"🔍 Checking backup table: {backup_table_id}")
    backup_info = get_table_info(client, backup_table_id)
    
    if not backup_info['exists']:
        logger.error(f"❌ Backup table does not exist: {backup_table_id}")
        print("💡 Use --list to see available backups")
        return False
    
    print(f"✅ Backup table found:")
    print(f"   Rows: {backup_info['row_count']:,}")
    print(f"   Schema fields: {backup_info['schema_fields']}")
    print(f"   Size: {backup_info['size_bytes']:,} bytes")
    print(f"   Created: {backup_info['created']}")
    print()
    
    # Check target table
    print(f"🔍 Checking target table: {target_table_id}")
    target_info = get_table_info(client, target_table_id)
    
    if target_info['exists']:
        print(f"⚠️  Target table exists:")
        print(f"   Current rows: {target_info['row_count']:,}")
        print(f"   Modified: {target_info['modified']}")
        print()
        print("⚠️  WARNING: This will OVERWRITE the current table!")
        print("⚠️  Make sure you have a backup of the current data!")
        print()
    
    # Confirm restore
    if not args.confirm:
        print("❌ Restore operation requires confirmation.")
        print("💡 Add --confirm flag to proceed with restore")
        return False
    
    # Perform restore
    print("🔄 Starting restore operation...")
    restore_success = restore_from_backup(client, backup_table_id, target_table_id, True)
    
    if not restore_success:
        logger.error("❌ Restore operation failed")
        return False
    
    # Verify restore
    print("🔍 Verifying restore...")
    final_info = get_table_info(client, target_table_id)
    
    if not final_info['exists']:
        logger.error("❌ Target table not found after restore")
        return False
    
    print()
    print("🎉 RESTORE COMPLETED SUCCESSFULLY!")
    print("=" * 50)
    print(f"✅ Restored from: {backup_table_id}")
    print(f"✅ Restored to: {target_table_id}")
    print(f"✅ Rows: {final_info['row_count']:,}")
    print(f"✅ Schema fields: {final_info['schema_fields']}")
    print()
    print("💡 The doctor profiles table has been restored from backup.")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
