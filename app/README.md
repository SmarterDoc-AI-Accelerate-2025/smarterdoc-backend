# SmarterDoc Backend API

Intelligent doctor search and AI-powered chat backend service

## Features

### 🔍 Core Features
- **Doctor Search** - Smart search based on conditions, location, and insurance
- **Intelligent Ranking** - Comprehensive scoring and ranking algorithms
- **Booking Service** - Doctor appointment booking API

### 🤖 AI Features
- **AI Chat** - Google Gemini-powered intelligent conversations
  - Streaming and non-streaming responses
  - Conversation history management
  - Custom system instructions
  
- **Speech-to-Text** - Google Cloud speech recognition
  - Real-time audio transcription (WebSocket)
  - Audio file transcription
  - Multi-language support
  - Browser microphone support

## Quick Start

### Prerequisites
- Python 3.11+
- Google Cloud project (for AI features)
- Elasticsearch (optional, for search functionality)

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Configure Environment Variables

Create a `.env` file:

```bash
# GCP Configuration
GCP_PROJECT_ID=your-project-id
GCP_REGION=us-central1

# Gemini Model Configuration
GEMINI_MODEL=gemini-2.5-flash-lite

# Speech-to-Text Configuration
SPEECH_LANGUAGE_CODE=en-US
SPEECH_SAMPLE_RATE=16000
SPEECH_ENABLE_AUTOMATIC_PUNCTUATION=True

# Elasticsearch (optional)
ELASTIC_URL=http://localhost:9200
```

### Run the Service

```bash
# Development mode
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or use Docker Compose (includes Elasticsearch)
docker compose up --build
```

### Access the API

- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Speech Demo**: http://localhost:8000/static/speech_demo.html

## API Endpoints Overview

### Doctor Search & Ranking
```
GET  /api/v1/search     - Search for doctors
POST /api/v1/rank       - Intelligent ranking
POST /api/v1/book       - Booking service
```

### AI Chat
```
POST /api/v1/chat/           - AI conversation
POST /api/v1/chat/stream     - Streaming AI conversation
GET  /api/v1/chat/health     - Service health check
```

### Speech-to-Text
```
POST /api/v1/speech/transcribe               - Transcribe audio file
POST /api/v1/speech/stream/upload            - Streaming transcription upload
WS   /api/v1/speech/stream/websocket         - WebSocket real-time transcription
GET  /api/v1/speech/health                   - Service health check
```

## Usage Examples

### AI Chat
```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8000/api/v1/chat/",
        json={
            "message": "Hello, please introduce yourself",
            "temperature": 0.7
        }
    )
    print(response.json()["message"])
```

### Streaming Chat
```python
import httpx

with httpx.Client() as client:
    with client.stream(
        'POST',
        'http://localhost:8000/api/v1/chat/stream',
        json={"message": "Tell me a story"}
    ) as response:
        for chunk in response.iter_text():
            print(chunk, end='', flush=True)
```

### Speech-to-Text
```python
import httpx

async with httpx.AsyncClient() as client:
    with open("audio.wav", "rb") as f:
        response = await client.post(
            "http://localhost:8000/api/v1/speech/transcribe",
            files={"file": f},
            params={"language_code": "en-US"}
        )
    print(response.json()["transcript"])
```

### WebSocket Real-time Transcription
Visit http://localhost:8000/static/speech_demo.html for a complete browser demo.

## Project Structure

```
app/
├── api/v1/              # API routes
│   ├── chat.py          # AI chat endpoints
│   ├── speech.py        # Speech transcription endpoints
│   ├── search.py        # Doctor search
│   ├── rank.py          # Ranking service
│   └── book.py          # Booking service
├── services/            # Business logic
│   ├── chat_service.py  # AI chat service
│   ├── speech_service.py # Speech transcription service
│   └── ...              # Other services
├── models/              # Data models
│   └── schemas.py       # Pydantic schemas
├── static/              # Static files
│   └── speech_demo.html # Speech demo page
├── config.py            # Configuration management
├── deps.py              # Dependency injection
└── main.py              # FastAPI application
```

## Google Cloud Authentication

### Local Development
```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

### Production
```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

### Enable Required APIs
- [Vertex AI API](https://console.cloud.google.com/apis/library/aiplatform.googleapis.com)
- [Cloud Speech-to-Text API](https://console.cloud.google.com/apis/library/speech.googleapis.com)

## Configuration

### AI Chat Settings
| Parameter | Default | Description |
|-----------|---------|-------------|
| `GEMINI_MODEL` | `gemini-2.5-flash-lite` | Model to use |
| `GENAI_TEMPERATURE` | `0.7` | Generation temperature (0.0-2.0) |
| `GENAI_MAX_OUTPUT_TOKENS` | `8192` | Maximum output tokens |

### Speech-to-Text Settings
| Parameter | Default | Description |
|-----------|---------|-------------|
| `SPEECH_LANGUAGE_CODE` | `en-US` | Language code |
| `SPEECH_SAMPLE_RATE` | `16000` | Audio sample rate (Hz) |
| `SPEECH_ENABLE_AUTOMATIC_PUNCTUATION` | `True` | Auto punctuation |

### Supported Languages
- `en-US` - English (United States)
- `zh-CN` - Chinese (Simplified)
- `zh-TW` - Chinese (Traditional)
- `ja-JP` - Japanese
- `es-ES` - Spanish
- `fr-FR` - French
- [More languages](https://cloud.google.com/speech-to-text/docs/languages)

## Docker Deployment

### Build Image
```bash
docker build -t smarterdoc-backend .
```

### Run Container
```bash
docker run -p 8000:8000 \
  -e GCP_PROJECT_ID=your-project-id \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json \
  -v /path/to/credentials.json:/app/credentials.json \
  smarterdoc-backend
```

### Docker Compose
```bash
docker compose up --build -d
```

## Troubleshooting

### Configuration Validation Failed
Ensure required environment variables are set:
```bash
export GCP_PROJECT_ID=your-project-id
export GCP_REGION=us-central1
```

### Empty Speech Transcription Results
Check audio file format:
- Format: LINEAR16 (16-bit PCM WAV)
- Sample Rate: 16000 Hz
- Channels: Mono

### Authentication Failed
```bash
# Check authentication status
gcloud auth list
gcloud config get-value project

# Re-authenticate
gcloud auth application-default login
```

## Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=app --cov-report=html

# Run specific test
pytest app/tests/test_api.py -v
```

## Resources

- [Google Vertex AI Documentation](https://cloud.google.com/vertex-ai/generative-ai/docs)
- [Google Cloud Speech-to-Text Documentation](https://cloud.google.com/speech-to-text/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Main Project README](../README.md)

## License

Follows the main repository's license.

---

**Need help?** Check the [API Documentation](http://localhost:8000/docs) or submit an issue.

