# NPI Registry API to CSV

极简的 NPI（National Provider Identifier）数据提取工具，直接调用 CMS 官方 API 并导出为 CSV。

## 工具选择

本项目提供四个工具，根据你的需求选择：

### 🚀 NPI_json_unlimited.py（JSON 无限制版，推荐数据分析）
- **场景**：突破 1200 条限制，获取完整原始 JSON 数据
- **输出**：符合 NPI Registry API v2.1 格式的 JSON 文件
- **配置**：分片策略（taxonomy/postal_code/last_name）
- **特色**：完整原始数据、嵌套结构、适合编程分析

### 🚀 NPI_csv_unlimited.py（CSV 无限制版，推荐大规模查询）
- **场景**：突破 1200 条限制，获取完整城市/州的医生数据
- **输出**：单个扁平化 CSV 文件（无数量限制）
- **配置**：分片策略（taxonomy/postal_code/last_name）
- **特色**：分片查询、全局去重、适合大城市

### 🎯 NPI_csv.py（简化版，推荐小规模查询）
- **场景**：快速获取特定城市的医生数据（< 1200 条）
- **输出**：单个扁平化 CSV 文件
- **配置**：修改文件顶部常量或使用命令行参数
- **特色**：专注个人医生、强大的重试机制、自动命名
- **限制**：最多 1200 条（API 限制）

### 📊 npi_to_csv.py（完整版，适合数据库导入）
- **场景**：需要规范化的关系型数据结构
- **输出**：三张规范化 CSV 表（providers/addresses/taxonomies）
- **配置**：丰富的命令行参数
- **特色**：支持个人和组织、灵活的查询条件
- **限制**：最多 1200 条（API 限制）

---

## 环境要求

- Python 3.7+
- 仅依赖 `requests` 库

## 安装

```bash
# 安装依赖
pip install -r requirements.txt

# 或直接安装
pip install -U requests
```

---

# 一、NPI_json_unlimited.py 使用指南（JSON 无限制版）

## 🎯 为什么选择 JSON 格式？

**NPI Registry API 的原始数据结构**：
- 保持完整的嵌套结构（basic、addresses、taxonomies 等）
- 包含所有原始字段（identifiers、endpoints、practice_locations 等）
- 便于编程分析和 API 集成
- 符合官方 v2.1 规范

**适用场景**：
- 需要深度数据分析
- 构建医疗数据应用
- 与现有 API 系统集成
- 需要完整原始数据

## 功能特点

- ✅ **突破 1200 限制**：通过智能分片策略获取完整数据
- ✅ **原始 JSON 格式**：完全保持 NPI Registry API 的数据结构
- ✅ **完整字段保留**：basic、addresses、taxonomies、identifiers、endpoints 等
- ✅ **三种分片策略**：按专科、邮编、姓氏首字母
- ✅ **全局去重**：跨分片自动去重，确保无重复
- ✅ **详细进度**：显示每个分片的查询进度

## JSON 输出格式

根据 [NPI Registry API v2.1 规范](https://npiregistry.cms.hhs.gov/api-page)，输出格式为：

```json
{
  "result_count": 1200,
  "results": [
    {
      "number": "1234567890",
      "enumeration_type": "NPI-1",
      "created_epoch": 1116806400,
      "last_updated_epoch": 1705276800,
      "basic": {
        "first_name": "JOHN",
        "last_name": "SMITH",
        "middle_name": "A",
        "credential": "MD",
        "gender": "M",
        "enumeration_date": "2005-05-23",
        "status": "A",
        "sole_proprietor": "YES",
        "name_prefix": "DR"
      },
      "other_names": [
        {
          "type": "Former Name",
          "last_name": "DOE",
          "first_name": "JOHN"
        }
      ],
      "identifiers": [
        {
          "identifier": "1234567",
          "code": "05",
          "desc": "MEDICAID",
          "state": "NY",
          "issuer": "NY MEDICAID"
        }
      ],
      "taxonomies": [
        {
          "code": "207RC0000X",
          "desc": "Cardiovascular Disease",
          "primary": true,
          "state": "NY",
          "license": "12345"
        }
      ],
      "addresses": [
        {
          "address_purpose": "MAILING",
          "address_1": "01 MAIN ST",
          "address_2": "STE 100",
          "city": "NEW YORK",
          "state": "NY",
          "postal_code": "10001",
          "telephone_number": "2125551234",
          "fax_number": "2125551235"
        },
        {
          "address_purpose": "LOCATION",
          "address_1": "01 MAIN ST",
          "address_2": "STE 100",
          "city": "NEW YORK",
          "state": "NY",
          "postal_code": "10001",
          "telephone_number": "2125555678",
          "fax_number": "2125555679"
        }
      ],
      "practice_locations": [
        {
          "address_1": "200 BROADWAY",
          "city": "NEW YORK",
          "state": "NY",
          "postal_code": "10007"
        }
      ],
      "endpoints": [
        {
          "endpointType": "DIRECT",
          "endpoint": "john.smith@direct.example.org",
          "endpoint_description": "Direct messaging address"
        }
      ]
    }
  ]
}
```

## 快速开始

### 方式一：修改配置文件

编辑 `NPI_json_unlimited.py` 顶部配置区：

```python
CITY = "New York"
STATE = "NY"
SHARDING_STRATEGY = "taxonomy"  # 选择分片策略
```

然后运行：
```bash
python NPI_json_unlimited.py
```

### 方式二：命令行参数

```bash
python NPI_json_unlimited.py <城市> <州> <策略>

# 示例
python NPI_json_unlimited.py "New York" "NY" "taxonomy"
python NPI_json_unlimited.py "Chicago" "IL" "last_name"
```

## 使用示例

### 示例 1：获取纽约市所有医生的完整 JSON 数据

```bash
python NPI_json_unlimited.py "New York" "NY" "taxonomy"
```

**输出示例**：
```
============================================================
开始分片查询：策略 = taxonomy
目标：New York, NY
============================================================

[信息] 正在获取 New York, NY 的所有专科列表...
[信息] 发现 45 个不同专科

[分片] 专科: Family Medicine
  skip=    0  fetched=200  added=200  shard_total= 200
  ...
  ✓ 分片 'Family Medicine' 完成：获取 856 条记录

[分片] 专科: Internal Medicine
  ...

============================================================
所有分片完成！
总计获取唯一 NPI: 15834 条
============================================================

[完成] 已保存 15834 条记录到 npi_doctors_NewYork_NY_unlimited.json
[信息] JSON 文件包含完整的 NPI Registry API 数据结构
```

## 数据分析示例

### Python 解析示例

```python
import json

# 读取 JSON 文件
with open('npi_doctors_NewYork_NY_unlimited.json', 'r') as f:
    data = json.load(f)

# 获取基本信息
print(f"总记录数: {data['result_count']}")

# 分析专科分布
taxonomy_count = {}
for record in data['results']:
    for taxonomy in record.get('taxonomies', []):
        desc = taxonomy.get('desc', '')
        if desc:
            taxonomy_count[desc] = taxonomy_count.get(desc, 0) + 1

# 显示最常见的专科
for desc, count in sorted(taxonomy_count.items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f"{desc}: {count}")

# 分析地址分布
address_count = {}
for record in data['results']:
    for address in record.get('addresses', []):
        if address.get('address_purpose') == 'LOCATION':
            city = address.get('city', '')
            if city:
                address_count[city] = address_count.get(city, 0) + 1

print(f"\n执业地址分布:")
for city, count in sorted(address_count.items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f"{city}: {count}")
```

### JavaScript 解析示例

```javascript
// 读取 JSON 文件
const fs = require('fs');
const data = JSON.parse(fs.readFileSync('npi_doctors_NewYork_NY_unlimited.json', 'utf8'));

console.log(`总记录数: ${data.result_count}`);

// 分析性别分布
const genderCount = {};
data.results.forEach(record => {
    const gender = record.basic?.gender || 'Unknown';
    genderCount[gender] = (genderCount[gender] || 0) + 1;
});

console.log('性别分布:', genderCount);

// 分析专科分布
const taxonomyCount = {};
data.results.forEach(record => {
    record.taxonomies?.forEach(taxonomy => {
        const desc = taxonomy.desc;
        if (desc) {
            taxonomyCount[desc] = (taxonomyCount[desc] || 0) + 1;
        }
    });
});

console.log('专科分布:', Object.entries(taxonomyCount)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10));
```

## 性能与时间估算

| 分片策略 | 分片数 | 估计时间* | 适用场景 |
|---------|-------|----------|---------|
| taxonomy | 35+ | 10-30 分钟 | 完整数据、深度分析 |
| last_name | 26 | 5-15 分钟 | 快速获取大部分 |
| postal_code | 自定义 | 取决于邮编数 | 区域分析 |

\* 时间取决于网络速度、API 响应、实际数据量

---

# 二、NPI_csv_unlimited.py 使用指南（CSV 无限制版）

## ⚠️ 为什么需要这个工具？

**NPI API 的硬性限制**：
- 单次查询最多返回 **1200 条唯一记录**
- 即使分页到 skip=10000，也只能获取前 1200 条
- 这是 CMS API 的官方限制，无法通过简单分页绕过

**解决方案**：
通过**分片查询**将大查询拆分成多个小查询，每个都在 1200 限制内，然后合并结果。

## 功能特点

- ✅ **突破 1200 限制**：通过智能分片策略获取完整数据
- ✅ **三种分片策略**：按专科、邮编、姓氏首字母
- ✅ **全局去重**：跨分片自动去重，确保无重复
- ✅ **详细进度**：显示每个分片的查询进度
- ✅ **自动合并**：最终输出单个完整 CSV 文件

## 分片策略详解

### 策略 1：按专科分片（taxonomy）⭐ 推荐

**原理**：分别查询每个专科的医生，然后合并

**优点**：
- ✅ 最精确，几乎无遗漏
- ✅ 每个专科下医生数通常 < 1200
- ✅ 结果自然分组，便于后续分析

**缺点**：
- ❌ 查询时间较长（需要查询 35+ 个专科）
- ❌ API 请求次数多

**适用场景**：需要完整数据、不着急的情况

**示例**：
```bash
python NPI_csv_unlimited.py "New York" "NY" "taxonomy"
```

### 策略 2：按姓氏首字母分片（last_name）

**原理**：分别查询姓氏以 A-Z 开头的医生

**优点**：
- ✅ 覆盖面广，适合任何城市
- ✅ 查询次数固定（26 次）

**缺点**：
- ❌ 某些字母（如 S、M）下医生可能 > 1200，仍会丢失
- ❌ 无法查询非英文姓氏

**适用场景**：快速获取大部分数据，可接受少量遗漏

**示例**：
```bash
python NPI_csv_unlimited.py "Los Angeles" "CA" "last_name"
```

### 策略 3：按邮编分片（postal_code）

**原理**：分别查询每个邮编区域的医生

**优点**：
- ✅ 地理分布清晰
- ✅ 每个邮编区域医生通常 < 1200

**缺点**：
- ❌ 需要提前知道所有邮编列表
- ❌ 配置较复杂

**适用场景**：已知邮编列表，需要按区域分析

**配置方式**：编辑 `NPI_csv_unlimited.py`
```python
SHARDING_STRATEGY = "postal_code"
POSTAL_CODES = ["07030", "07302", "07306", ...]  # 填入邮编列表
```

**示例**：
```bash
python NPI_csv_unlimited.py "Jersey City" "NJ" "postal_code"
```

## 快速开始

### 方式一：修改配置文件

编辑 `NPI_csv_unlimited.py` 顶部配置区：

```python
CITY = "New York"
STATE = "NY"
SHARDING_STRATEGY = "taxonomy"  # 选择分片策略
```

然后运行：
```bash
python NPI_csv_unlimited.py
```

### 方式二：命令行参数

```bash
python NPI_csv_unlimited.py <城市> <州> <策略>

# 示例
python NPI_csv_unlimited.py "New York" "NY" "taxonomy"
python NPI_csv_unlimited.py "Chicago" "IL" "last_name"
```

## 使用示例

### 示例 1：获取纽约市所有医生

```bash
python NPI_csv_unlimited.py "New York" "NY" "taxonomy"
```

**输出示例**：
```
============================================================
开始分片查询：策略 = taxonomy
目标：New York, NY
============================================================

[分片] 专科: Family Medicine
  skip=    0  fetched=200  added=200  shard_total= 200
  skip=  200  fetched=200  added=200  shard_total= 400
  ...
  ✓ 分片 'Family Medicine' 完成：获取 856 条记录

[分片] 专科: Internal Medicine
  skip=    0  fetched=200  added=200  shard_total= 200
  ...
  ✓ 分片 'Internal Medicine' 完成：获取 1124 条记录

[分片] 专科: Pediatrics
  ...

============================================================
所有分片完成！
总计获取唯一 NPI: 15834 条
============================================================

[完成] 已保存 15834 条记录到 npi_doctors_NewYork_NY_unlimited.csv
```

### 示例 2：自定义专科列表

如果只关心某几个专科，可以修改 `COMMON_TAXONOMIES` 列表：

```python
COMMON_TAXONOMIES = [
    "Family Medicine",
    "Internal Medicine",
    "Pediatrics",
    # 只查询这三个专科
]
```

### 示例 3：添加更多专科

```python
COMMON_TAXONOMIES = [
    # ... 原有专科 ...
    
    # 添加非医生类别
    "Nurse Practitioner",
    "Physician Assistant",
    "Clinical Psychologist",
]
```

## 性能与时间估算

| 分片策略 | 分片数 | 估计时间* | 适用场景 |
|---------|-------|----------|---------|
| taxonomy | 35+ | 10-30 分钟 | 完整数据、不着急 |
| last_name | 26 | 5-15 分钟 | 快速获取大部分 |
| postal_code | 自定义 | 取决于邮编数 | 区域分析 |

\* 时间取决于网络速度、API 响应、实际数据量

## 常见问题

### Q: 为什么 taxonomy 策略查询时间这么长？

A: 需要分别查询 35+ 个专科，每个专科可能有数百条记录。可以：
1. 减少 `COMMON_TAXONOMIES` 列表中的专科数量
2. 增大 `time.sleep()` 间隔避免限流
3. 使用 `last_name` 策略作为替代

### Q: last_name 策略会遗漏数据吗？

A: 可能。如果某个字母下医生 > 1200，会触发限制。建议与 taxonomy 策略结合使用验证。

### Q: 如何验证数据完整性？

A: 可以：
1. 用不同策略查询，对比结果数量
2. 检查输出文件中的 `practice_postal_code` 分布
3. 与官方统计数据对比（如果有）

### Q: 能否组合多种策略？

A: 当前版本不支持。如需组合，可以：
1. 分别运行两次，生成两个 CSV
2. 使用 Python/Excel 合并并去重

---

# 二、NPI_csv.py 使用指南

## 功能特点

- ✅ 配置简单：修改文件顶部配置区即可
- ✅ 单文件输出：所有数据扁平化在一个 CSV 中
- ✅ 专注医生：仅获取个人提供者（NPI-1），过滤执业地址
- ✅ 智能重试：网络错误自动重试，指数退避
- ✅ 自动命名：根据城市/州/专科自动生成文件名
- ✅ 去重保护：自动过滤重复 NPI

## 快速开始

### 方式一：修改配置文件

编辑 `NPI_csv.py` 顶部配置区：

```python
# ====== 配置区 ======
CITY = "Boston"          # 目标城市
STATE = "MA"             # 州缩写（强烈建议填写）
TAXONOMY_DESC = ""       # 专科过滤（例如 "Family Medicine"、"Pediatrics"；留空则不过滤）
ADDRESS_PURPOSE = "location"   # 只匹配执业地址：location（避免混入邮寄地址）
ENUMERATION_TYPE = "NPI-1"     # 个人提供者（医生）
API_VERSION = "2.1"
PAGE_LIMIT = 200          # NPI API 单页最大 200
REQUEST_TIMEOUT = 30      # 每次请求超时（秒）
MAX_RETRIES = 5           # 网络错误重试次数
RETRY_BACKOFF = 2.0       # 重试指数退避基数（秒）
OUTPUT_FILE = None        # 若为 None 则自动按城市州命名
# ====================
```

然后运行：

```bash
python NPI_csv.py
```

### 方式二：命令行参数

```bash
# 查询波士顿所有医生
python NPI_csv.py "Boston" "MA"

# 查询波士顿的家庭医学医生
python NPI_csv.py "Boston" "MA" "Family Medicine"

# 查询洛杉矶的心脏科医生
python NPI_csv.py "Los Angeles" "CA" "Cardiology"
```

## 使用示例

### 1. 获取特定城市的所有医生

```python
CITY = "Seattle"
STATE = "WA"
TAXONOMY_DESC = ""  # 不限专科
```

输出：`npi_doctors_Seattle_WA.csv`

### 2. 获取特定专科医生

```python
CITY = "New York"
STATE = "NY"
TAXONOMY_DESC = "Pediatrics"
```

输出：`npi_doctors_NewYork_NY_Pediatrics.csv`

### 3. 自定义输出文件名

```python
CITY = "Chicago"
STATE = "IL"
OUTPUT_FILE = "chicago_doctors_2024.csv"
```

输出：`chicago_doctors_2024.csv`

## 输出 CSV 字段说明

单个 CSV 文件包含以下字段：

| 字段 | 说明 |
|------|------|
| **基本信息** | |
| npi | NPI 唯一标识 |
| enumeration_type | 实体类型（通常为 NPI-1） |
| name | 医生全名（first + middle + last） |
| credential | 资质证书（如 MD, DO, NP） |
| gender | 性别 |
| enumeration_date | 首次登记日期 |
| last_updated | 最后更新日期 |
| **专科信息** | |
| all_taxonomy_codes | 所有专科代码（用分号分隔） |
| **执业地址** | |
| practice_address_1 | 执业地址第一行 |
| practice_address_2 | 执业地址第二行 |
| practice_city | 执业城市 |
| practice_state | 执业州 |
| practice_postal_code | 邮政编码 |
| practice_country_code | 国家代码 |
| practice_phone | 执业电话 |
| practice_fax | 执业传真 |
| **其他** | |
| sole_proprietor | 是否独资经营 |
| status | 状态（A=激活） |

## 配置参数详解

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| CITY | str | "Boston" | 目标城市名称 |
| STATE | str | "MA" | 州缩写（2位字母） |
| TAXONOMY_DESC | str | "" | 专科描述筛选，留空则不过滤 |
| ADDRESS_PURPOSE | str | "location" | 地址类型：location（执业）或 mailing（邮寄） |
| ENUMERATION_TYPE | str | "NPI-1" | NPI-1（个人）或 NPI-2（组织） |
| PAGE_LIMIT | int | 200 | 每页数据量（最大200） |
| REQUEST_TIMEOUT | int | 30 | 请求超时秒数 |
| MAX_RETRIES | int | 5 | 网络错误最大重试次数 |
| RETRY_BACKOFF | float | 2.0 | 重试退避基数（指数增长） |
| OUTPUT_FILE | str/None | None | 输出文件名，None则自动生成 |

## 常见问题

### Q: 如何获取组织（医院、诊所）数据？

修改配置：
```python
ENUMERATION_TYPE = "NPI-2"
```

### Q: 如何同时获取邮寄地址和执业地址？

此工具专注于执业地址。如需多地址，请使用 `npi_to_csv.py`。

### Q: 如何加速数据获取？

1. 减少 `REQUEST_TIMEOUT`（如果网络稳定）
2. 添加 `time.sleep()` 可以缩短或去掉（156行）
3. 确保州（STATE）参数已填写，缩小查询范围

### Q: 运行时遇到网络错误？

工具已内置重试机制。如果持续失败：
1. 检查网络连接
2. 增大 `MAX_RETRIES` 和 `REQUEST_TIMEOUT`
3. 增大 `RETRY_BACKOFF`

---

# 二、npi_to_csv.py 使用指南

## 功能特点

- ✅ 直接调用 NPI Registry API，无需数据库
- ✅ 支持按姓名、州、城市、专科等多维度筛选
- ✅ 自动分页，完整获取所有匹配数据
- ✅ 导出三张规范化 CSV 表：
  - `providers.csv` - 医疗提供者主信息
  - `addresses.csv` - 地址信息（邮寄/执业地址）
  - `taxonomies.csv` - 专业分类信息
- ✅ 自动去重、错误重试、智能退避

## 使用示例

### 1. 按州 + 专科筛选

查询纽约州所有家庭医学医生：

```bash
python npi_to_csv.py --state NY --taxonomy "Family Medicine" --limit 200
```

### 2. 按姓名 + 城市筛选

查询 Rochester 市名为 John Smith 的医生：

```bash
python npi_to_csv.py --first-name John --last-name Smith --city Rochester
```

### 3. 精确查询某个 NPI

```bash
python npi_to_csv.py --npi 1234567890
```

### 4. 组合条件查询

查询加州洛杉矶的心脏科医生：

```bash
python npi_to_csv.py --state CA --city "Los Angeles" --taxonomy "Cardiology"
```

### 5. 自定义输出文件名

```bash
python npi_to_csv.py --state TX --taxonomy "Dentist" \
  --out-providers texas_dentists.csv \
  --out-addresses texas_dentists_addr.csv \
  --out-taxonomies texas_dentists_tax.csv
```

## 命令行参数

### 筛选条件

| 参数 | 说明 | 示例 |
|------|------|------|
| `--first-name` | 医生名字 | `--first-name John` |
| `--last-name` | 医生姓氏 | `--last-name Smith` |
| `--state` | 美国州代码（2位） | `--state NY` |
| `--city` | 城市名称 | `--city Rochester` |
| `--taxonomy` | 专科代码或描述 | `--taxonomy "Family Medicine"` |
| `--npi` | 精确 NPI 号码 | `--npi 1234567890` |

### 性能调优

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--limit` | 每页数据量（1-200） | 200 |
| `--sleep` | 每页间隔秒数 | 0.2 |

### 输出文件

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--out-providers` | 主信息 CSV | `providers.csv` |
| `--out-addresses` | 地址 CSV | `addresses.csv` |
| `--out-taxonomies` | 专科 CSV | `taxonomies.csv` |

## 输出 CSV 说明

### providers.csv

医疗提供者主信息表：

| 字段 | 说明 |
|------|------|
| npi | NPI 唯一标识 |
| enumeration_date | 登记日期 |
| last_updated | 最后更新日期 |
| entity_type | 实体类型（个人/组织） |
| first_name, last_name | 姓名（个人） |
| org_name | 组织名称 |
| gender | 性别 |
| credential | 资质证书 |
| status | 状态 |

### addresses.csv

地址信息表（一对多）：

| 字段 | 说明 |
|------|------|
| npi | 关联的 NPI |
| address_purpose | 地址类型（MAILING/LOCATION） |
| address_1, address_2 | 街道地址 |
| city, state, postal_code | 城市、州、邮编 |
| telephone_number, fax_number | 电话、传真 |

### taxonomies.csv

专业分类表（一对多）：

| 字段 | 说明 |
|------|------|
| npi | 关联的 NPI |
| taxonomy_code | 专科代码 |
| taxonomy_desc | 专科描述 |
| primary | 是否主要专科 |
| state | 州执照 |
| license | 执照号码 |

## 注意事项

1. **Taxonomy 参数**：
   - 可以传入代码（如 `207Q00000X`）
   - 也可以传入描述（如 `"Family Medicine"`）
   - 脚本会自动识别并使用正确的 API 参数

2. **分页机制**：
   - API 单次最多返回 200 条
   - 脚本自动翻页直到数据耗尽
   - 使用 `skip` 参数进行偏移

3. **限流保护**：
   - 默认每页间隔 0.2 秒
   - HTTP 错误自动重试（最多 5 次）
   - 指数退避策略

4. **数据去重**：
   - 自动跟踪已获取的 NPI
   - 避免重复数据

## 示例输出

```
[INFO] got 200 rows (skip=0), total providers=200
[INFO] got 200 rows (skip=200), total providers=400
[INFO] got 157 rows (skip=400), total providers=557
[DONE]
 providers:  providers.csv  (rows=557)
 addresses:  addresses.csv  (rows=1114)
 taxonomies: taxonomies.csv (rows=892)
```

## 数据来源

数据来自美国 CMS（Centers for Medicare & Medicaid Services）官方 NPI Registry API：
https://npiregistry.cms.hhs.gov/api/

## License

MIT License

