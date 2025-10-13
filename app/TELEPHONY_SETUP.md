# Twilio + Vertex AI Live API 电话集成指南

## 概述

本系统实现了 Twilio 电话系统与 Google Vertex AI Live API 的实时语音对话桥接，支持：
- 双向语音流（Twilio ⇄ FastAPI ⇄ Vertex AI Live API）
- 实时音频编解码（μ-law 8kHz ⇄ PCM16 16kHz/24kHz）
- 外呼和来电支持
- 多语音模型选择
- 自定义系统指令

## 架构

```
电话用户 ⇄ Twilio ⇄ WebSocket ⇄ FastAPI Backend ⇄ Vertex AI Live API
         (8kHz μ-law)       (实时桥接)      (16kHz/24kHz PCM16)
```

### 核心组件

1. **音频编解码** (`app/util/audio_codec.py`)
   - μ-law ↔ PCM16 转换
   - 采样率转换 (8kHz ↔ 16kHz ↔ 24kHz)

2. **Vertex Live 服务** (`app/services/vertex_live_service.py`)
   - Vertex AI Live API 会话管理
   - 实时音频流处理

3. **Twilio 服务** (`app/services/telephony.py`)
   - Twilio 外呼管理
   - WebSocket 媒体流处理

4. **API 端点** (`app/api/v1/telephony.py`)
   - POST `/api/v1/telephony/call` - 发起外呼
   - GET `/api/v1/telephony/twiml` - TwiML 生成
   - WS `/api/v1/telephony/twilio-stream` - 媒体流桥接

## 1. 本地环境准备

### 1.1 GCP/Vertex AI 准备

1. **启用必要的 API**
```bash
gcloud services enable aiplatform.googleapis.com
```

2. **设置认证**
```bash
gcloud auth application-default login
export GOOGLE_CLOUD_PROJECT=你的项目ID
export GOOGLE_CLOUD_LOCATION=us-central1
```

3. **验证权限**
确保服务账号有以下权限：
- `Vertex AI User`
- `AI Platform Developer`

### 1.2 Twilio 准备

1. **获取 Twilio 凭证**
   - 登录 [Twilio Console](https://console.twilio.com/)
   - 获取 Account SID 和 Auth Token
   - 购买或配置一个电话号码

2. **配置 Twilio 号码**
   - 在 Twilio Console 中配置号码的 Voice webhook
   - 稍后会填入你的公网 URL

### 1.3 Python 环境

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 1.4 环境变量配置

创建 `.env` 文件：

```bash
# GCP 配置
GCP_PROJECT_ID=your-gcp-project-id
GCP_REGION=us-central1

# Twilio 配置
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_NUMBER=+1234567890

# Vertex AI Live API 配置
VERTEX_LIVE_MODEL=gemini-2.0-flash-exp
VERTEX_LIVE_VOICE=Puck
VERTEX_LIVE_SYSTEM_INSTRUCTION=你是一个专业的医疗助手，语气自然、简短直接。

# 其他配置...
ENVIRONMENT=dev
PORT=8080
```

### 可用的语音选项
- `Puck` - 男声（活泼）
- `Charon` - 男声（沉稳）
- `Kore` - 女声（温和）
- `Fenrir` - 男声（专业）
- `Aoede` - 女声（友好）

## 2. 本地运行与测试

### 2.1 启动本地服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

服务将在 `http://localhost:8080` 启动。

### 2.2 使用 ngrok 暴露公网

Twilio 需要公网 URL 来回调你的服务。使用 ngrok：

```bash
# 安装 ngrok (如果还没有)
# macOS: brew install ngrok
# 或从 https://ngrok.com/download 下载

# 启动 ngrok
ngrok http 8080
```

你会得到类似这样的 URL：
```
https://1234-56-78-90-123.ngrok-free.app
```

记下这个 URL，这是你的 **公网地址**。

### 2.3 测试 API 端点

#### 健康检查
```bash
curl http://localhost:8080/api/v1/telephony/health
```

#### 发起测试外呼
```bash
curl -X POST http://localhost:8080/api/v1/telephony/call \
  -H "Content-Type: application/json" \
  -d '{
    "to": "+1234567890",
    "voice": "Puck",
    "system_instruction": "你是一个电话助手"
  }'
```

响应：
```json
{
  "success": true,
  "call_sid": "CA1234567890abcdef",
  "message": "Call initiated to +1234567890"
}
```

#### 查询通话状态
```bash
curl http://localhost:8080/api/v1/telephony/call/CA1234567890abcdef
```

#### 挂断通话
```bash
curl -X POST http://localhost:8080/api/v1/telephony/call/CA1234567890abcdef/hangup
```

### 2.4 测试完整流程

1. **启动本地服务**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

2. **启动 ngrok**
```bash
ngrok http 8080
```

3. **发起测试外呼**
```bash
curl -X POST http://localhost:8080/api/v1/telephony/call \
  -H "Content-Type: application/json" \
  -d '{
    "to": "+1你的手机号"
  }'
```

4. **接听电话**
   - 你会收到电话
   - 接听后可以直接和 AI 助手对话
   - AI 会实时回复

### 2.5 回声测试（可选）

在接入 Vertex Live 之前，可以先做一个简单的回声测试，确保双向音频流正常：

修改 `app/services/telephony.py` 中的 `process_twilio_audio` 方法，直接返回收到的音频：

```python
async def process_twilio_audio(self, payload_base64: str) -> Optional[bytes]:
    # 简单回声测试：直接返回收到的音频
    ulaw_8k = base64.b64decode(payload_base64)
    return ulaw_8k  # 直接返回，形成回声
```

打电话测试，如果能听到自己的回声，说明双向流是通的。

## 3. 部署到 Cloud Run

### 3.1 构建 Docker 镜像

确保 `Dockerfile` 包含必要的依赖：

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 设置环境变量
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# 启动命令
CMD exec uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### 3.2 构建和推送镜像

```bash
# 设置项目 ID
export PROJECT_ID=your-gcp-project-id
export REGION=us-central1

# 构建镜像
gcloud builds submit --tag gcr.io/$PROJECT_ID/smarterdoc-backend

# 或使用 Docker
docker build -t gcr.io/$PROJECT_ID/smarterdoc-backend .
docker push gcr.io/$PROJECT_ID/smarterdoc-backend
```

### 3.3 部署到 Cloud Run

```bash
gcloud run deploy smarterdoc-backend \
  --image gcr.io/$PROJECT_ID/smarterdoc-backend \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID,GCP_REGION=$REGION" \
  --set-env-vars "VERTEX_LIVE_MODEL=gemini-2.0-flash-exp" \
  --set-env-vars "VERTEX_LIVE_VOICE=Puck" \
  --set-secrets "TWILIO_ACCOUNT_SID=twilio-account-sid:latest" \
  --set-secrets "TWILIO_AUTH_TOKEN=twilio-auth-token:latest" \
  --set-secrets "TWILIO_NUMBER=twilio-number:latest" \
  --min-instances 1 \
  --max-instances 10 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --concurrency 80
```

### 3.4 配置 Secret Manager（推荐）

```bash
# 创建 secrets
echo -n "your-twilio-sid" | gcloud secrets create twilio-account-sid --data-file=-
echo -n "your-twilio-token" | gcloud secrets create twilio-auth-token --data-file=-
echo -n "+1234567890" | gcloud secrets create twilio-number --data-file=-

# 授权 Cloud Run 访问 secrets
gcloud secrets add-iam-policy-binding twilio-account-sid \
  --member=serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor
```

### 3.5 获取部署 URL

```bash
gcloud run services describe smarterdoc-backend \
  --platform managed \
  --region $REGION \
  --format 'value(status.url)'
```

你会得到类似：`https://smarterdoc-backend-xxxxx.run.app`

## 4. 配置 Twilio Webhook

### 4.1 在 Twilio Console 配置

1. 登录 [Twilio Console](https://console.twilio.com/)
2. 进入 **Phone Numbers** → **Active Numbers**
3. 选择你的号码
4. 在 **Voice Configuration** 部分：
   - **A CALL COMES IN**: Webhook
   - **URL**: `https://your-domain.com/api/v1/telephony/twiml`
   - **HTTP**: POST
5. 保存配置

### 4.2 测试来电

配置完成后，拨打你的 Twilio 号码，应该能够与 AI 助手对话。

## 5. API 使用示例

### 5.1 发起外呼（基础）

```python
import requests

response = requests.post(
    "https://your-domain.com/api/v1/telephony/call",
    json={
        "to": "+1234567890"
    }
)

print(response.json())
# {"success": true, "call_sid": "CA...", "message": "..."}
```

### 5.2 发起外呼（自定义语音）

```python
response = requests.post(
    "https://your-domain.com/api/v1/telephony/call",
    json={
        "to": "+1234567890",
        "voice": "Kore",
        "system_instruction": "你是一个预约助手，帮助患者预约医生。"
    }
)
```

### 5.3 查询通话状态

```python
call_sid = "CA1234567890abcdef"
response = requests.get(
    f"https://your-domain.com/api/v1/telephony/call/{call_sid}"
)

print(response.json())
# {"sid": "CA...", "status": "in-progress", "duration": null, ...}
```

### 5.4 挂断通话

```python
response = requests.post(
    f"https://your-domain.com/api/v1/telephony/call/{call_sid}/hangup"
)

print(response.json())
# {"success": true, "message": "Call CA... hung up"}
```

## 6. 生产环境优化

### 6.1 性能调优

**并发处理**
```python
# 在 config.py 中调整
VERTEX_LIVE_MAX_CONCURRENT_SESSIONS = 50
TWILIO_WEBSOCKET_TIMEOUT = 300
```

**音频缓冲**
```python
# 在 audio_codec.py 中可以添加缓冲机制
class AudioBuffer:
    def __init__(self, buffer_ms=100):
        self.buffer_ms = buffer_ms
        self.buffer = []
```

### 6.2 错误处理和重试

```python
# 在 vertex_live_service.py 中添加重试逻辑
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
async def send_audio_with_retry(self, audio_data: bytes):
    await self.send_audio(audio_data)
```

### 6.3 监控和日志

**Cloud Logging**
```python
# 在 logging.py 中配置 Google Cloud Logging
from google.cloud import logging as cloud_logging

client = cloud_logging.Client()
client.setup_logging()
```

**监控指标**
- WebSocket 连接数
- 音频处理延迟
- Vertex API 响应时间
- 错误率

### 6.4 断线恢复

```python
# 在 telephony.py 中添加断线重连
async def reconnect_with_backoff(self, max_retries=3):
    for attempt in range(max_retries):
        try:
            await self.vertex_session.connect()
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
            else:
                raise
```

## 7. 故障排查

### 7.1 常见问题

**问题：Twilio 连接失败**
```
检查：
1. 公网 URL 是否可访问（curl https://your-domain.com/health）
2. Twilio webhook 配置是否正确
3. 防火墙是否开放 443 端口
```

**问题：音频质量差**
```
检查：
1. 采样率转换是否正确
2. 音频缓冲是否足够
3. 网络延迟（ping 和 traceroute）
```

**问题：Vertex API 超时**
```
检查：
1. GCP 认证是否正确
2. Vertex API 是否启用
3. 区域配置是否匹配（us-central1）
```

### 7.2 调试技巧

**启用详细日志**
```python
# 在 config.py 中
LOGGING_LEVEL = "DEBUG"
```

**音频调试**
```python
# 保存音频到文件进行检查
with open("debug_audio.raw", "wb") as f:
    f.write(audio_data)

# 使用 ffplay 播放 PCM16
ffplay -f s16le -ar 16000 -ac 1 debug_audio.raw
```

**WebSocket 调试**
```bash
# 使用 wscat 测试 WebSocket
npm install -g wscat
wscat -c wss://your-domain.com/api/v1/telephony/twilio-stream
```

## 8. 安全考虑

### 8.1 认证和授权

```python
# 在 telephony.py 中添加 API key 验证
from fastapi import Header, HTTPException

async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != settings.API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
```

### 8.2 Twilio 签名验证

```python
from twilio.request_validator import RequestValidator

def validate_twilio_request(request: Request):
    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)
    params = dict(request.form)
    
    if not validator.validate(url, params, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")
```

### 8.3 速率限制

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/call")
@limiter.limit("10/minute")
async def initiate_call(request: Request, ...):
    ...
```

## 9. 成本估算

### 9.1 Twilio 成本
- **外呼**: ~$0.013/分钟（美国）
- **来电**: ~$0.0085/分钟（美国）
- **电话号码**: ~$1/月

### 9.2 Google Cloud 成本
- **Vertex AI Live API**: 参考最新定价
- **Cloud Run**: 
  - CPU: ~$0.00002400/vCPU-second
  - Memory: ~$0.00000250/GiB-second
  - 免费额度: 2M 请求/月

### 9.3 优化建议
1. 使用 Cloud Run 的最小实例数=0（开发环境）
2. 合理设置超时时间
3. 监控并发连接数
4. 使用区域化部署减少延迟

## 10. 下一步

### 10.1 功能增强
- [ ] 添加通话录音功能
- [ ] 实现多方通话
- [ ] 添加 DTMF（按键）支持
- [ ] 集成 CRM 系统
- [ ] 添加情感分析

### 10.2 集成医疗功能
- [ ] 患者信息查询
- [ ] 医生预约系统
- [ ] 处方查询
- [ ] 病历摘要

## 参考文档

- [Twilio Media Streams](https://www.twilio.com/docs/voice/media-streams)
- [Vertex AI Live API](https://cloud.google.com/vertex-ai/generative-ai/docs/live-api)
- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)
- [ngrok 文档](https://ngrok.com/docs)

## 支持

如有问题，请查看：
1. 日志文件：`/var/log/app/telephony.log`
2. Cloud Run 日志：`gcloud run logs read smarterdoc-backend`
3. Twilio 调试控制台：https://console.twilio.com/monitor/logs

---

**祝你部署顺利！** 🎉

