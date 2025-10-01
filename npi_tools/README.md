# NPI Data Extraction Tool

Advanced NPI Registry API data extraction tool that breaks through the 1200-record API limit using intelligent multi-level sharding strategy.

## 🎯 Key Features

- ✅ **Break 1200 Limit**: Multi-level sharding strategy to fetch unlimited records
- ✅ **Complete Data**: Collect all specialties by scanning postal codes  
- ✅ **Smart Subdivision**: Automatically subdivide by postal code when specialty exceeds 1200
- ✅ **Global Deduplication**: Ensure unique NPI records across all queries
- ✅ **Original JSON Format**: Maintain complete NPI Registry API data structure
- ✅ **Progress Tracking**: Real-time display of query progress

## 📊 Performance Comparison

| City | Old Method | New Multi-level Method | Improvement |
|------|-----------|----------------------|-------------|
| **New York, NY** | 10,384 records | **73,581 records** | **7x improvement** ✨ |
| **Hoboken, NJ** | 992 records | 992 records | Complete data ✅ |

## 🚀 Quick Start

### Installation

```bash
# Install dependencies
pip install requests
```

### Basic Usage

```bash
# Fetch complete data for a city
python NPI_multilevel_shard.py "New York" "NY"

# Fetch data for another city
python NPI_multilevel_shard.py "Los Angeles" "CA"

# The tool will automatically:
# 1. Scan all postal codes in the city
# 2. Discover all medical specialties
# 3. Query each specialty
# 4. Subdivide by postal code if specialty exceeds 1200 records
```

### Output

- **File**: `npi_doctors_NewYork_NY_multilevel.json`
- **Format**: Complete NPI Registry API JSON structure
- **Content**: All NPI-1 type healthcare providers in the specified city

## 🔧 How It Works

### Multi-level Sharding Strategy

```
Step 1: Postal Code Collection
├─ Traverse first 1200 records
└─ Extract all unique postal codes

Step 2: Specialty Discovery  
├─ Query first 200 records from each postal code
└─ Collect all unique specialties (no omissions)

Step 3: Data Retrieval
├─ Query by specialty
└─ If reaches 1200 limit → Subdivide by postal code
    ├─ Query each specialty + postal code combination
    └─ Ensure all data is retrieved
```

### Example: New York City

```
Total postal codes: 300+
Total specialties: 100+
Specialties exceeding 1200:
  - Student in an Organized Health Care Education/Training Program: 1200+ → Subdivided by postal code
  - Internal Medicine: 1200+ → Subdivided by postal code
  
Final result: 73,581 unique NPI records (vs 10,384 with old method)
```

## 📝 Configuration

Edit configuration in `NPI_multilevel_shard.py`:

```python
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
OUTPUT_FILE = None  # Auto-generate if None
# ====================
```

## 🔍 Data Analysis

Use `analyze_taxonomy.py` to analyze the distribution of medical specialties:

```bash
python analyze_taxonomy.py
```

**Output**:
- Total record count
- Unique specialty descriptions
- Unique specialty codes  
- Top 20 most common specialties
- Complete specialty list (alphabetically sorted)

## 📌 Important Notes

### API Rate Limits

The NPI Registry API has rate limiting. If you encounter `403 Forbidden` errors:

1. **Wait 10-15 minutes** for the rate limit to reset
2. The tool already includes delays (0.2-0.3s between requests)
3. For very large cities, the query may take 5-10 minutes

### City Name Format

Use exact city names as they appear in the NPI database:

✅ Correct:
- `"New York"` (not "New York City")
- `"Los Angeles"`
- `"Chicago"`

❌ Incorrect:
- `"NYC"` or `"New York city"` (limited data)

### Data Completeness

The multi-level sharding strategy ensures:
- All postal codes are scanned
- All specialties are discovered
- Specialties exceeding 1200 are automatically subdivided
- No data loss due to API limits

## 🛠️ Technical Details

### API Limitations

The NPI Registry API has a hard limit:
- **Maximum 1200 records** per single query combination
- When `skip >= 1200`, API returns duplicate data
- Cannot bypass through simple pagination

### Solution: Intelligent Sharding

```
Problem: Single specialty > 1200 records
Solution: Specialty + Postal Code subdivision

Example: "Internal Medicine" in New York
├─ Direct query: 1200 records (limited)
└─ Subdivide by postal code:
    ├─ Internal Medicine + 10001: 150 records
    ├─ Internal Medicine + 10002: 98 records
    ├─ ... (all postal codes)
    └─ Total: 1500+ unique records ✅
```

## 📦 Output Format

The output JSON file follows the NPI Registry API v2.1 structure:

```json
{
  "result_count": 73581,
  "results": [
    {
      "number": "1234567890",
      "enumeration_type": "NPI-1",
      "basic": {
        "first_name": "John",
        "last_name": "Smith",
        "credential": "MD",
        ...
      },
      "addresses": [...],
      "taxonomies": [...],
      "identifiers": [...],
      "endpoints": [...]
    },
    ...
  ]
}
```

## 🔗 Resources

- [NPI Registry API Documentation](https://npiregistry.cms.hhs.gov/api-page)
- [NPPES NPI Registry](https://npiregistry.cms.hhs.gov/)
- [CMS National Plan and Provider Enumeration System](https://www.cms.gov/Regulations-and-Guidance/Administrative-Simplification/NationalProvIdentStand)

## 💡 Tips

1. **Start with small cities** to test (e.g., Hoboken, NJ)
2. **Be patient** with large cities (may take 5-10 minutes)
3. **Check output file** immediately if process is interrupted
4. **Use analyze_taxonomy.py** to understand specialty distribution
5. **Respect API limits** - don't run multiple instances simultaneously

## 📄 License

MIT License

---

**Built with ❤️ for healthcare data researchers**

