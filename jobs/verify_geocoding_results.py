#!/usr/bin/env python3
"""
Verify geocoding results
"""

import os
from app.deps import get_bq_sync

def verify_geocoding_results():
    """Verify that the geocoding was successful."""
    client = get_bq_sync()
    
    query = """
    SELECT 
        npi,
        first_name,
        last_name,
        latitude,
        longitude,
        updated_at
    FROM `1094971678787.curated.doctor_profiles`
    WHERE CAST(npi AS STRING) IN ("1235426610", "1376943910")
    ORDER BY npi
    """
    
    result = list(client.query(query))
    
    print('🎉 更新结果验证:')
    print('=' * 50)
    
    for row in result:
        print(f'✅ NPI: {row.npi}')
        print(f'   姓名: {row.first_name} {row.last_name}')
        print(f'   纬度: {row.latitude}')
        print(f'   经度: {row.longitude}')
        print(f'   更新时间: {row.updated_at}')
        print()
    
    # Check overall status
    status_query = """
    SELECT 
        COUNT(*) as total_doctors,
        COUNT(CASE WHEN latitude IS NULL OR longitude IS NULL THEN 1 END) as missing_coords
    FROM `1094971678787.curated.doctor_profiles`
    """
    
    status_result = list(client.query(status_query))
    total = status_result[0].total_doctors
    missing = status_result[0].missing_coords
    
    print('📊 整体状态:')
    print(f'   总医生数: {total}')
    print(f'   缺少坐标: {missing}')
    print(f'   完成率: {((total-missing)/total*100):.1f}%')
    
    if missing == 0:
        print('🎉 所有医生都已成功获取坐标！')
    else:
        print(f'⚠️ 还有 {missing} 个医生缺少坐标')

if __name__ == "__main__":
    verify_geocoding_results()
