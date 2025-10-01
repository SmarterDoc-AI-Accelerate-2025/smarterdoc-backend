# 快速开始指南

## 🚨 你遇到了 1200 条限制吗？

如果你看到类似的日志：
```
[INFO] skip=19200 fetched=200 added=0 total=1200
[INFO] skip=19400 fetched=200 added=0 total=1200
```

这说明你触发了 **NPI API 的 1200 条硬性限制**。

---

## 解决方案：使用无限制版本

### 📥 安装依赖

```bash
pip install -r requirements.txt
```

### 🚀 运行无限制版本

#### 方法 1：JSON 格式（推荐数据分析）

```bash
python NPI_json_unlimited.py "Your City" "State" "taxonomy"
```

**示例**：
```bash
# 获取纽约市所有医生（JSON 格式）
python NPI_json_unlimited.py "New York" "NY" "taxonomy"

# 获取霍博肯所有医生（JSON 格式）
python NPI_json_unlimited.py "Hoboken" "NJ" "taxonomy"
```

**预期输出**：
- 文件名：`npi_doctors_Hoboken_NJ_unlimited.json`
- 格式：**完整的 NPI Registry API v2.1 JSON 结构**
- 数量：**突破 1200 限制**，获取所有医生
- 数据：包含 basic、addresses、taxonomies、identifiers、endpoints 等完整字段

**时间**：10-30 分钟（取决于城市大小）

---

#### 方法 2：CSV 格式（推荐表格分析）

#### 方法 1：按专科分片（推荐，最完整）

```bash
python NPI_csv_unlimited.py "Your City" "State" "taxonomy"
```

**示例**：
```bash
# 获取纽约市所有医生
python NPI_csv_unlimited.py "New York" "NY" "taxonomy"

# 获取霍博肯所有医生
python NPI_csv_unlimited.py "Hoboken" "NJ" "taxonomy"
```

**预期输出**：
- 文件名：`npi_doctors_Hoboken_NJ_unlimited.csv`
- 数量：**突破 1200 限制**，获取所有医生
- 新字段：`all_taxonomy_codes`（所有专科代码，用分号分隔）

**时间**：10-30 分钟（取决于城市大小）

---

#### 方法 2：按姓氏首字母分片（更快，可能略有遗漏）

```bash
python NPI_csv_unlimited.py "Your City" "State" "last_name"
```

**示例**：
```bash
python NPI_csv_unlimited.py "Los Angeles" "CA" "last_name"
```

**预期输出**：
- 覆盖大部分医生（95%+）
- 某些常见姓氏首字母（S、M）可能仍有遗漏

**时间**：5-15 分钟

---

## 📊 四种工具对比

| 工具 | 适用场景 | 数量限制 | 输出格式 | 速度 |
|------|---------|---------|---------|------|
| **NPI_json_unlimited.py** | 数据分析，需要原始结构 | ❌ 无限制 | JSON | 慢（10-30分钟） |
| **NPI_csv_unlimited.py** | 大城市，需要完整数据 | ❌ 无限制 | CSV | 慢（10-30分钟） |
| **NPI_csv.py** | 小城市，快速查询 | ✅ 最多 1200 | CSV | 快（1-3分钟） |
| **npi_to_csv.py** | 需要规范化表结构 | ✅ 最多 1200 | CSV | 快（1-3分钟） |

---

## 💡 使用建议

### 如果你的城市医生 < 1200
使用 `NPI_csv.py`（简单快速）

### 如果你的城市医生 > 1200
使用 `NPI_csv_unlimited.py`（完整数据）

### 如何判断是否超过 1200？
运行 `NPI_csv.py`，看最终数量：
- 如果 < 1200 且日志显示正常终止 → 数据完整
- 如果 = 1200 且连续多页 `added=0` → **触发限制，数据不完整**

---

## 🔧 配置示例

### Hoboken, NJ（你的当前配置）

```bash
# 快速测试（可能只有 1200）
python NPI_csv.py

# 完整数据（突破限制）
python NPI_csv_unlimited.py "Hoboken" "NJ" "taxonomy"
```

### 纽约市（大城市）

```bash
# 完整数据（按专科分片）
python NPI_csv_unlimited.py "New York" "NY" "taxonomy"

# 或者更快的方式（按姓氏分片）
python NPI_csv_unlimited.py "New York" "NY" "last_name"
```

---

## 📝 详细文档

查看完整使用说明：[NPI_USAGE.md](./NPI_USAGE.md)

---

## ❓ 常见问题

**Q: 为什么会有 1200 条限制？**  
A: 这是 CMS NPI Registry API 的官方限制，无法通过简单分页绕过。

**Q: 无限制版本需要多久？**  
A: 10-30 分钟，取决于城市大小和网络速度。

**Q: 会不会被 API 封禁？**  
A: 不会。脚本内置了合理的限速（每页间隔 0.3 秒）。

**Q: 数据会重复吗？**  
A: 不会。脚本有全局去重机制，确保每个 NPI 只出现一次。

