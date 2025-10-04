# PubMed Article Search Tool via ORCID

这个工具用于搜索NPI数据库中每个医生在PubMed上的文章，通过ORCID进行精确匹配。

## 功能

- 读取NPI医生数据库（包括NPI号、姓名、地址）
- **第一步**：使用姓名和地址在ORCID数据库中搜索医生的ORCID ID
- **第二步**：使用ORCID ID在PubMed中搜索文章（更准确）
- 保存ORCID和文章链接到JSON文件
- 支持进度保存（每50个医生保存一次）
- 自动处理API速率限制
- 提供详细统计信息（ORCID匹配率、文章数量等）

## 使用方法

### 1. 安装依赖

```bash
pip install requests
```

### 2. 配置

编辑 `search_pubmed.py` 文件中的配置：

- `EMAIL`: **必须**设置你的邮箱（NCBI要求）
- `API_KEY`: 可选，添加NCBI API密钥以提高速率限制
  - 获取API密钥：https://www.ncbi.nlm.nih.gov/account/settings/
- `MAX_DOCTORS`: 测试时建议设为小数字（如10），设为None处理所有医生
- `USE_LOCATION_FILTER`: 是否在ORCID搜索中使用州信息
  - **False（默认推荐）**：仅使用姓名搜索，更准确
  - True：包含州信息过滤，可能降低匹配率

### 3. 运行

```bash
cd pubmed_tool
python search_pubmed.py
```

## 工作流程（带智能Fallback机制）

1. **读取NPI数据**：从JSON文件读取医生信息（NPI号、姓名、城市、州、专业taxonomy）

2. **搜索ORCID**：使用医生姓名在ORCID.org搜索匹配的研究人员
   - **默认**：仅使用姓名搜索（更准确）
   - **可选**：可以启用州信息过滤（设置 `USE_LOCATION_FILTER = True`）

3. **搜索PubMed（智能策略）**：
   - **第一步**：如果找到ORCID，使用ORCID在PubMed搜索
   - **第二步（Fallback）**：如果ORCID搜索无结果或没有ORCID，使用 **姓名 + 专业领域** 搜索
   - **第三步**：如果仍无结果，返回空

4. **保存结果**：保存ORCID、搜索方法、文章链接和详细统计信息

## 重要说明：为什么不使用城市/州搜索？

**默认情况下，ORCID搜索只使用医生姓名，不使用城市或州信息。**

原因：
- ❌ 城市名称（如"NEW YORK"）**不是**医院或机构名称
- ❌ 使用城市/州作为机构名称会导致搜索失败或不准确
- ✅ 仅使用姓名搜索，让ORCID返回最相关的匹配结果
- ✅ 如果需要，可以手动启用州过滤，但可能会降低匹配率

## 输出格式

输出文件 `pubmed_articles_results.json` 包含：

```json
{
  "statistics": {
    "total_processed": 10,
    "orcid_found": 3,
    "orcid_not_found": 7,
    "with_articles": 6,
    "total_articles": 45,
    "search_methods": {
      "orcid": 2,
      "orcid_found_but_fallback_to_name": 1,
      "name_and_specialty": 3,
      "no_results": 4
    }
  },
  "doctors": [
    {
      "npi": "1285902783",
      "first_name": "JOHN",
      "last_name": "SMITH",
      "credential": "M.D.",
      "taxonomy": "Internal Medicine",
      "city": "NEW YORK",
      "state": "NY",
      "orcid": "0000-0001-2345-6789",
      "search_method": "orcid",
      "article_count": 15,
      "article_links": [
        "https://pubmed.ncbi.nlm.nih.gov/12345678/",
        "https://pubmed.ncbi.nlm.nih.gov/87654321/"
      ]
    },
    {
      "npi": "9876543210",
      "first_name": "JANE",
      "last_name": "DOE",
      "credential": "M.D.",
      "taxonomy": "Cardiologist",
      "city": "BROOKLYN",
      "state": "NY",
      "orcid": null,
      "search_method": "name_and_specialty",
      "article_count": 8,
      "article_links": [...]
    }
  ]
}
```

### 搜索方法说明

- `orcid`: 通过ORCID成功找到文章
- `orcid_found_but_fallback_to_name`: 找到ORCID但PubMed中无结果，使用姓名+专业找到文章
- `name_and_specialty`: 没有ORCID，使用姓名+专业找到文章
- `no_results`: 所有方法都未找到文章

## 注意事项

⚠️ **重要提醒**

1. **处理时间**: NPI文件包含73,581位医生，完整处理需要很长时间
   - 每个医生需要2次API调用（ORCID搜索 + PubMed搜索）
   - 估计总时间：约12-15小时（包含速率限制延迟）
   
2. **API速率限制**: 
   - ORCID API：每秒2次请求（0.5秒延迟）
   - PubMed API：
     - 无API密钥：每秒3次请求
     - 有API密钥：每秒10次请求

3. **开始测试**: 建议先设置 `MAX_DOCTORS = 10` 进行测试

4. **邮箱必填**: 必须设置有效邮箱地址，否则NCBI可能阻止请求

5. **进度保存**: 程序每处理50个医生会自动保存进度

6. **ORCID匹配率**: 
   - 不是所有医生都有ORCID账号
   - 仅医学研究人员可能有ORCID
   - 预期匹配率：约5-15%

7. **数据准确性**: 
   - 使用ORCID匹配比纯姓名搜索更准确
   - 避免同名医生的混淆
   - 确保文章归属正确

## API文档

- ORCID Public API: https://info.orcid.org/documentation/features/public-api/
- PubMed E-utilities API: https://www.ncbi.nlm.nih.gov/books/NBK25501/

## 优势

### 智能搜索策略的优势：

1. ✅ **多层次搜索**：ORCID优先，姓名+专业fallback，最大化覆盖率
2. ✅ **精确匹配**：ORCID是全球唯一的研究人员标识符
3. ✅ **避免同名混淆**：使用专业领域作为额外筛选条件
4. ✅ **高覆盖率**：即使没有ORCID，也能通过姓名+专业找到文章
5. ✅ **透明追溯**：每条记录都标注了使用的搜索方法
6. ✅ **详细统计**：清晰展示各种搜索方法的效果

