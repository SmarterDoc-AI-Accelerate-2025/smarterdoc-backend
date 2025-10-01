# smarterdoc-backend

NPI Registry API 数据提取工具 - 从 CMS 官方 API 获取医疗提供者数据并导出为 CSV。

## 快速开始

### ⚠️ 遇到 1200 条限制？

如果你发现数据停留在 1200 条且无法增加，请查看：
👉 **[突破限制快速指南](./QUICK_START.md)**

### 安装依赖

```bash
pip install -r requirements.txt
```

## 工具对比

本项目提供四个不同的 NPI 数据提取工具，根据需求选择：

### 🚀 NPI_json_unlimited.py - JSON 无限制版（推荐大规模查询）

**适用场景**：需要获取某城市/州的**完整**医生数据（突破 1200 条限制），且需要原始 JSON 格式

**特点**：
- ✅ **突破 API 限制**：通过分片查询突破 1200 条上限
- ✅ **原始 JSON 格式**：保持 NPI Registry API 的完整数据结构
- ✅ 三种分片策略：按专科、邮编、姓氏首字母
- ✅ 全局去重：跨分片自动去重
- ✅ 详细进度：显示每个分片的查询进度
- ✅ 适合大数据分析：保留所有原始字段和嵌套结构

**基本用法**：

```bash
# 按专科分片（推荐，最精确）
python NPI_json_unlimited.py "New York" "NY" "taxonomy"

# 按姓氏首字母分片（覆盖面广）
python NPI_json_unlimited.py "Los Angeles" "CA" "last_name"

# 或直接运行（使用文件内配置）
python NPI_json_unlimited.py
```

**输出**：`npi_doctors_NewYork_NY_unlimited.json`（包含完整的 NPI Registry API 数据结构）

---

### 🚀 NPI_csv_unlimited.py - CSV 无限制版（推荐大规模查询）

**适用场景**：需要获取某城市/州的**完整**医生数据（突破 1200 条限制）

**特点**：
- ✅ **突破 API 限制**：通过分片查询突破 1200 条上限
- ✅ 三种分片策略：按专科、邮编、姓氏首字母
- ✅ 全局去重：跨分片自动去重
- ✅ 详细进度：显示每个分片的查询进度
- ✅ 适合大城市：纽约、洛杉矶等医生数量 > 1200 的城市

**基本用法**：

```bash
# 按专科分片（推荐，最精确）
python NPI_csv_unlimited.py "New York" "NY" "taxonomy"

# 按姓氏首字母分片（覆盖面广）
python NPI_csv_unlimited.py "Los Angeles" "CA" "last_name"

# 或直接运行（使用文件内配置）
python NPI_csv_unlimited.py
```

**输出**：`npi_doctors_NewYork_NY_unlimited.csv`（包含所有医生，无数量限制）

**新特性**：
- ✅ 动态获取所有专科（不再使用预定义列表）
- ✅ 返回所有 `taxonomy_code` 原始数据（用分号分隔）
- ✅ 删除主要专科字段，获取完整专科信息

---

### 📄 NPI_json_unlimited.py - JSON 无限制版（推荐数据分析）

**适用场景**：需要原始 JSON 格式进行深度数据分析

**特点**：
- ✅ **完整原始数据**：保持 NPI Registry API 的完整 JSON 结构
- ✅ **所有字段保留**：basic、addresses、taxonomies、identifiers、endpoints 等
- ✅ **嵌套结构**：保持原始的对象和数组结构
- ✅ **适合编程**：便于 JSON 解析和 API 集成

**基本用法**：

```bash
# 获取完整 JSON 数据
python NPI_json_unlimited.py "New York" "NY" "taxonomy"
```

**输出**：`npi_doctors_NewYork_NY_unlimited.json`（符合 NPI Registry API v2.1 格式）

---

### 1️⃣ NPI_csv.py - 简化版（推荐小规模查询）

**适用场景**：快速获取特定城市的医生数据（< 1200 条）

**特点**：
- ✅ 配置简单，修改文件顶部配置即可
- ✅ 单文件扁平化输出，便于直接使用
- ✅ 专注个人医生（NPI-1），过滤执业地址
- ✅ 自动命名输出文件
- ✅ 强大的网络重试机制
- ⚠️ **限制**：单次查询最多 1200 条（API 限制）

**基本用法**：

```bash
# 直接运行（使用文件内配置）
python NPI_csv.py

# 或使用命令行参数
python NPI_csv.py "Boston" "MA" "Family Medicine"
```

**配置方式**：编辑 `NPI_csv.py` 顶部配置区：

```python
CITY = "Boston"          # 目标城市
STATE = "MA"             # 州缩写
TAXONOMY_DESC = ""       # 专科过滤（如 "Family Medicine"）
PAGE_LIMIT = 200         # 每页数量
```

**输出**：单个 CSV 文件（如 `npi_doctors_Boston_MA.csv`），包含完整信息

---

### 2️⃣ npi_to_csv.py - 完整版

**适用场景**：需要规范化数据库结构或复杂查询

**特点**：
- ✅ 命令行参数丰富
- ✅ 生成三张规范化 CSV 表（providers, addresses, taxonomies）
- ✅ 支持个人和组织类型
- ✅ 更灵活的筛选条件

**基本用法**：

```bash
# 按州 + 专科筛选
python npi_to_csv.py --state NY --taxonomy "Family Medicine"

# 按姓名查询
python npi_to_csv.py --first-name John --last-name Smith

# 精确 NPI 查询
python npi_to_csv.py --npi 1234567890
```

**输出**：三个 CSV 文件
- `providers.csv` - 医疗提供者主信息
- `addresses.csv` - 地址信息（邮寄/执业）
- `taxonomies.csv` - 专业分类信息

---

## 详细文档

完整使用说明请查看 [NPI_USAGE.md](./NPI_USAGE.md)

## 环境要求

- Python 3.7+
- requests 库

## License

MIT License