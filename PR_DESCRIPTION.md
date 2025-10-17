# PR: 新增智能排序搜索API端点

## 📋 概述

本PR在rank模块中新增了一个智能排序搜索API端点，将搜索和排序功能整合到一个API调用中，提供更智能的医生推荐服务。

## 🎯 主要变更

### 1. 新增API端点
- **端点**: `POST /api/v1/rank/search-rank`
- **功能**: 搜索医生并通过ranker进行智能排序
- **返回格式**: 与现有search API保持一致

### 2. 新增数据模型
在 `app/models/schemas.py` 中添加了新的请求模型：
```python
class FrontendRankSearchRequest(BaseModel):
    specialty: Optional[str] = None
    insurance: Optional[str] = None
    location: Optional[str] = None
    userinput: Optional[str] = None
```

### 3. 核心功能实现
在 `app/api/v1/rank.py` 中实现了：
- `search_and_rank_doctors()`: 主要API处理函数
- `parse_location()`: 位置解析功能
- `convert_to_doctor_hits()`: 数据格式转换
- `convert_to_frontend_format()`: 排序结果转换

## 🔄 处理流程

1. **搜索阶段**: 通过BigQuery搜索基础医生列表
2. **转换阶段**: 将DoctorOut转换为DoctorHit格式
3. **排序阶段**: 调用现有rank_candidates函数进行智能排序
4. **返回阶段**: 转换回前端格式并保持排序顺序

## 📊 API规格

### 请求格式
```json
{
  "specialty": "string",     // 医生专科
  "insurance": "string",     // 保险计划
  "location": "string",      // 位置信息
  "userinput": "string"      // 用户文本输入
}
```

### 响应格式
```json
{
  "search_query": "string",
  "total_results": 123,
  "doctors": [
    {
      "npi": "string",
      "first_name": "string",
      "last_name": "string",
      "primary_specialty": "string",
      // ... 其他DoctorOut字段
    }
  ]
}
```

## ✅ 特性

- **智能排序**: 利用现有ranker的AI能力进行个性化推荐
- **数据兼容**: 返回格式与现有search API完全一致
- **模块化设计**: 保持搜索和排序逻辑的分离
- **向后兼容**: 不影响现有API的正常使用
- **扩展性**: 可轻松添加更多排序因子

## 🚀 使用场景

前端可以通过调用此API获得：
1. 基于专科的基础搜索
2. 考虑保险和位置的智能排序
3. 结合用户文本输入的个性化推荐

## 📝 注意事项

- 位置解析功能目前使用默认值，后续可集成地理编码服务
- 搜索参数(min_experience, has_certification, limit)使用固定默认值
- 保持与现有API架构的一致性

## 🔗 相关文件

- `app/api/v1/rank.py` - 新增API端点实现
- `app/models/schemas.py` - 新增数据模型
- `app/services/ranker.py` - 现有排序服务
- `app/services/bq_doctor_service.py` - 现有搜索服务
