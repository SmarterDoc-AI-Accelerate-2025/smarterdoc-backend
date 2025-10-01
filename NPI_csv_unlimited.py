#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NPI 数据提取工具 - 无限制版本
通过分片查询策略突破 API 的 1200 条限制
"""

import csv
import time
import sys
import requests
from typing import Dict, Any, List, Optional, Tuple, Set

# ====== 配置区 ======
CITY = "Hoboken"
STATE = "NJ"
ADDRESS_PURPOSE = "location"
ENUMERATION_TYPE = "NPI-1"
API_VERSION = "2.1"
PAGE_LIMIT = 200
REQUEST_TIMEOUT = 30
MAX_RETRIES = 5
RETRY_BACKOFF = 2.0
OUTPUT_FILE = None

# 分片策略选择：
# "taxonomy" - 按专科分片（推荐，最精确）
# "postal_code" - 按邮编分片（需要提供邮编列表）
# "last_name" - 按姓氏首字母分片（覆盖面广但可能遗漏）
# "none" - 不分片（单次查询，受 1200 限制）
SHARDING_STRATEGY = "taxonomy"

# 当 SHARDING_STRATEGY = "taxonomy" 时，将动态获取所有专科
# 不再使用预定义的 COMMON_TAXONOMIES 列表

# 姓氏首字母分片（当 SHARDING_STRATEGY = "last_name" 时使用）
LAST_NAME_PREFIXES = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

# 邮编列表（当 SHARDING_STRATEGY = "postal_code" 时使用）
POSTAL_CODES = []  # 例如: ["07030", "07302", "07306"]
# ====================


def build_params(city: str, state: str, skip: int, **kwargs) -> Dict[str, str]:
    """构建 API 请求参数"""
    params = {
        "version": API_VERSION,
        "city": city,
        "state": state,
        "enumeration_type": ENUMERATION_TYPE,
        "address_purpose": ADDRESS_PURPOSE,
        "limit": str(PAGE_LIMIT),
        "skip": str(skip),
    }
    
    # 添加额外的过滤参数
    if "taxonomy_description" in kwargs and kwargs["taxonomy_description"]:
        params["taxonomy_description"] = kwargs["taxonomy_description"]
    if "taxonomy_code" in kwargs and kwargs["taxonomy_code"]:
        params["taxonomy"] = kwargs["taxonomy_code"]  # 注意：API 中专科代码用 taxonomy 参数
    if "postal_code" in kwargs and kwargs["postal_code"]:
        params["postal_code"] = kwargs["postal_code"]
    if "last_name" in kwargs and kwargs["last_name"]:
        params["last_name"] = kwargs["last_name"]
    
    return params


def get_taxonomy_codes_for_description(city: str, state: str, taxonomy_desc: str) -> List[str]:
    """获取特定专科描述下的所有专科代码"""
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
        
        code_set = set()
        for rec in results:
            taxonomies = rec.get("taxonomies", []) or []
            for tax in taxonomies:
                desc = tax.get("desc", "") or tax.get("taxonomy_description", "")
                if desc == taxonomy_desc:
                    code = tax.get("code", "")
                    if code:
                        code_set.add(code)
        
        code_list = sorted(list(code_set))
        print(f"[信息] 专科 '{taxonomy_desc}' 下发现 {len(code_list)} 个不同代码")
        return code_list
        
    except Exception as e:
        print(f"[警告] 获取专科代码失败: {e}")
        return []


def request_with_retries(url: str, params: Dict[str, str]) -> Dict[str, Any]:
    """带重试机制的 HTTP 请求"""
    last_err = None
    for i in range(MAX_RETRIES):
        try:
            r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
            sleep_s = (RETRY_BACKOFF ** i)
            time.sleep(sleep_s)
    raise RuntimeError(f"请求失败（已重试 {MAX_RETRIES} 次）: {last_err}")


def select_location_address(addresses: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """优先返回 purpose == 'LOCATION' 的地址"""
    if not addresses:
        return None
    for a in addresses:
        if str(a.get("address_purpose", "")).lower() == "location":
            return a
    return addresses[0]


def get_all_taxonomies(taxonomies: List[Dict[str, Any]]) -> str:
    """返回所有专科代码，用分号分隔"""
    if not taxonomies:
        return ""
    codes = []
    for t in taxonomies:
        code = t.get("code", "")
        if code:
            codes.append(code)
    return ";".join(codes)


def phones_from_addresses(addresses: List[Dict[str, Any]]) -> Tuple[str, str]:
    """返回（执业电话，执业传真）"""
    addr = select_location_address(addresses or [])
    if not addr:
        return ("", "")
    return (
        addr.get("telephone_number", "") or "",
        addr.get("fax_number", "") or "",
    )


def flatten_record(rec: Dict[str, Any]) -> Dict[str, Any]:
    """将 API 返回的记录扁平化"""
    basic = rec.get("basic", {}) or {}
    addresses = rec.get("addresses", []) or []
    taxonomies = rec.get("taxonomies", []) or []

    addr = select_location_address(addresses)
    tel, fax = phones_from_addresses(addresses)
    all_taxonomy_codes = get_all_taxonomies(taxonomies)

    first = basic.get("first_name", "")
    last = basic.get("last_name", "")
    middle = basic.get("middle_name", "")
    name = " ".join([p for p in [first, middle, last] if p]).strip() or basic.get("name", "")

    return {
        "npi": rec.get("number", ""),
        "enumeration_type": rec.get("enumeration_type", ""),
        "name": name,
        "credential": basic.get("credential", ""),
        "gender": basic.get("gender", ""),
        "enumeration_date": basic.get("enumeration_date", ""),
        "last_updated": basic.get("last_updated", ""),
        "all_taxonomy_codes": all_taxonomy_codes,
        "practice_address_1": (addr or {}).get("address_1", ""),
        "practice_address_2": (addr or {}).get("address_2", ""),
        "practice_city": (addr or {}).get("city", ""),
        "practice_state": (addr or {}).get("state", ""),
        "practice_postal_code": (addr or {}).get("postal_code", ""),
        "practice_country_code": (addr or {}).get("country_code", ""),
        "practice_phone": tel,
        "practice_fax": fax,
        "sole_proprietor": basic.get("sole_proprietor", ""),
        "status": basic.get("status", ""),
    }


def fetch_single_shard(city: str, state: str, shard_name: str, **shard_params) -> List[Dict[str, Any]]:
    """获取单个分片的数据"""
    base = "https://npiregistry.cms.hhs.gov/api/"
    all_rows: List[Dict[str, Any]] = []
    seen_npi = set()
    skip = 0
    consecutive_empty = 0
    MAX_CONSECUTIVE_EMPTY = 3
    
    print(f"\n[分片] {shard_name}")
    
    while True:
        params = build_params(city, state, skip, **shard_params)
        data = request_with_retries(base, params)
        batch = data.get("results", []) or []
        
        added = 0
        for rec in batch:
            npi = rec.get("number")
            if npi and npi not in seen_npi:
                flat = flatten_record(rec)
                all_rows.append(flat)
                seen_npi.add(npi)
                added += 1
        
        print(f"  skip={skip:5d}  fetched={len(batch):3d}  added={added:3d}  shard_total={len(all_rows):4d}")
        
        # 检查是否继续
        if added == 0:
            consecutive_empty += 1
            if consecutive_empty >= MAX_CONSECUTIVE_EMPTY:
                break
        else:
            consecutive_empty = 0
        
        if len(batch) < PAGE_LIMIT:
            break
        
        skip += PAGE_LIMIT
        time.sleep(0.3)
    
    print(f"  ✓ 分片 '{shard_name}' 完成：获取 {len(all_rows)} 条记录")
    return all_rows


def get_all_taxonomies_from_api(city: str, state: str) -> List[str]:
    """从 API 获取所有可能的专科列表"""
    print(f"\n[信息] 正在获取 {city}, {state} 的所有专科列表...")
    
    # 先进行一次无专科过滤的查询，获取所有专科
    base = "https://npiregistry.cms.hhs.gov/api/"
    params = {
        "version": API_VERSION,
        "city": city,
        "state": state,
        "enumeration_type": ENUMERATION_TYPE,
        "address_purpose": ADDRESS_PURPOSE,
        "limit": "200",
        "skip": "0",
    }
    
    try:
        data = request_with_retries(base, params)
        results = data.get("results", []) or []
        
        taxonomy_set = set()
        for rec in results:
            taxonomies = rec.get("taxonomies", []) or []
            for tax in taxonomies:
                desc = tax.get("desc", "") or tax.get("taxonomy_description", "")
                if desc:
                    taxonomy_set.add(desc)
        
        taxonomy_list = sorted(list(taxonomy_set))
        print(f"[信息] 发现 {len(taxonomy_list)} 个不同专科")
        return taxonomy_list
        
    except Exception as e:
        print(f"[警告] 获取专科列表失败: {e}")
        print(f"[信息] 使用默认专科列表")
        # 如果失败，使用一个基本的专科列表
        return [
            "Family Medicine", "Internal Medicine", "Pediatrics", 
            "Psychiatry & Neurology", "Obstetrics & Gynecology",
            "Orthopedic Surgery", "General Surgery", "Cardiology",
            "Dermatology", "Emergency Medicine", "Radiology",
            "Anesthesiology", "Pathology", "Physical Medicine & Rehabilitation",
            "Ophthalmology", "Otolaryngology", "Urology", "Neurology",
            "Psychiatry", "Preventive Medicine", "Plastic Surgery",
            "Allergy & Immunology", "Geriatric Medicine", "Infectious Disease",
            "Nephrology", "Pulmonary Disease", "Rheumatology", "Sports Medicine",
            "Hematology & Oncology", "Gastroenterology", "Endocrinology",
            "Critical Care Medicine", "Pain Medicine", "Sleep Medicine",
            "Hospice and Palliative Medicine", "Addiction Medicine"
        ]


def fetch_all_with_sharding(city: str, state: str, strategy: str) -> List[Dict[str, Any]]:
    """使用分片策略获取所有数据"""
    all_rows: List[Dict[str, Any]] = []
    global_seen_npi: Set[str] = set()
    
    print(f"\n{'='*60}")
    print(f"开始分片查询：策略 = {strategy}")
    print(f"目标：{city}, {state}")
    print(f"{'='*60}")
    
    if strategy == "taxonomy":
        # 按专科分片 - 使用多重细分策略突破1200限制
        shards = get_all_taxonomies_from_api(city, state)
        for taxonomy in shards:
            print(f"\n[信息] 开始查询专科: {taxonomy}")
            
            # 先按专科描述查询
            rows = fetch_single_shard(
                city, state, 
                shard_name=f"专科描述: {taxonomy}",
                taxonomy_description=taxonomy
            )
            
            # 如果这个专科获取的记录数达到1200，使用多重细分策略
            if len(rows) >= 1200:
                print(f"[警告] 专科 '{taxonomy}' 达到1200条限制，使用多重细分策略...")
                
                # 策略1: 按专科代码细分
                taxonomy_codes = get_taxonomy_codes_for_description(city, state, taxonomy)
                for code in taxonomy_codes:
                    print(f"[信息] 查询专科代码: {code}")
                    code_rows = fetch_single_shard(
                        city, state,
                        shard_name=f"专科代码: {code}",
                        taxonomy_code=code
                    )
                    
                    # 如果专科代码也达到1200，进一步按姓氏首字母细分
                    if len(code_rows) >= 1200:
                        print(f"[警告] 专科代码 '{code}' 也达到1200条限制，按姓氏首字母细分...")
                        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                            letter_rows = fetch_single_shard(
                                city, state,
                                shard_name=f"代码+姓氏: {code}+{letter}*",
                                taxonomy_code=code,
                                last_name=f"{letter}*"
                            )
                            # 全局去重
                            for row in letter_rows:
                                npi = row.get("npi")
                                if npi and npi not in global_seen_npi:
                                    all_rows.append(row)
                                    global_seen_npi.add(npi)
                    else:
                        # 全局去重
                        for row in code_rows:
                            npi = row.get("npi")
                            if npi and npi not in global_seen_npi:
                                all_rows.append(row)
                                global_seen_npi.add(npi)
            else:
                # 全局去重
                for row in rows:
                    npi = row.get("npi")
                    if npi and npi not in global_seen_npi:
                        all_rows.append(row)
                        global_seen_npi.add(npi)
    
    elif strategy == "postal_code":
        # 按邮编分片
        if not POSTAL_CODES:
            print("[错误] 策略为 'postal_code' 但未提供邮编列表（POSTAL_CODES）")
            return []
        
        for postal in POSTAL_CODES:
            rows = fetch_single_shard(
                city, state,
                shard_name=f"邮编: {postal}",
                postal_code=postal
            )
            for row in rows:
                npi = row.get("npi")
                if npi and npi not in global_seen_npi:
                    all_rows.append(row)
                    global_seen_npi.add(npi)
    
    elif strategy == "last_name":
        # 按姓氏首字母分片
        for letter in LAST_NAME_PREFIXES:
            rows = fetch_single_shard(
                city, state,
                shard_name=f"姓氏: {letter}*",
                last_name=f"{letter}*"
            )
            for row in rows:
                npi = row.get("npi")
                if npi and npi not in global_seen_npi:
                    all_rows.append(row)
                    global_seen_npi.add(npi)
    
    elif strategy == "none":
        # 不分片，单次查询（受 1200 限制）
        rows = fetch_single_shard(city, state, shard_name="单次查询（无分片）")
        all_rows = rows
    
    else:
        print(f"[错误] 未知的分片策略: {strategy}")
        return []
    
    print(f"\n{'='*60}")
    print(f"所有分片完成！")
    print(f"总计获取唯一 NPI: {len(all_rows)} 条")
    print(f"{'='*60}\n")
    
    return all_rows


def write_csv(rows: List[Dict[str, Any]], filepath: str) -> None:
    """写入 CSV 文件"""
    if not rows:
        fieldnames = [
            "npi","enumeration_type","name","credential","gender",
            "enumeration_date","last_updated",
            "all_taxonomy_codes",
            "practice_address_1","practice_address_2","practice_city","practice_state",
            "practice_postal_code","practice_country_code","practice_phone","practice_fax",
            "sole_proprietor","status"
        ]
    else:
        fieldnames = list(rows[0].keys())

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def sanitize_filename_part(s: str) -> str:
    """清理文件名"""
    return "".join(c for c in s if c.isalnum() or c in ("-", "_")).strip("_") or "x"


def main():
    city = CITY
    state = STATE
    strategy = SHARDING_STRATEGY
    
    # 支持命令行参数
    if len(sys.argv) >= 3:
        city = sys.argv[1]
        state = sys.argv[2]
    if len(sys.argv) >= 4:
        strategy = sys.argv[3]
    
    # 执行查询
    rows = fetch_all_with_sharding(city, state, strategy)
    
    # 生成输出文件名
    if OUTPUT_FILE:
        out = OUTPUT_FILE
    else:
        out = f"npi_doctors_{sanitize_filename_part(city)}_{sanitize_filename_part(state)}_unlimited.csv"
    
    write_csv(rows, out)
    print(f"[完成] 已保存 {len(rows)} 条记录到 {out}")


if __name__ == "__main__":
    main()

