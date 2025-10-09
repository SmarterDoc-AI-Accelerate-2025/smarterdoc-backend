# AI Chat Service

A production-ready AI chat service powered by Google Vertex AI and Gemini models. This service provides RESTful APIs for both streaming and non-streaming chat interactions with conversation history support.

## 📋 Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Documentation](#api-documentation)
- [Testing](#testing)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

## ✨ Features

### Chat Features
- **Streaming & Non-Streaming Chat**: Support for both real-time streaming and complete responses
- **Conversation History**: Multi-turn conversations with context preservation
- **Flexible Configuration**: Environment-based configuration with sensible defaults
- **System Instructions**: Customize AI behavior with system prompts
- **Token Usage Tracking**: Monitor token consumption for cost management

### Speech-to-Text Features
- **Microphone Transcription**: Real-time speech-to-text from microphone input
- **Audio File Transcription**: Transcribe uploaded audio files
- **Streaming Recognition**: Get interim and final transcription results
- **Multi-language Support**: Support for multiple languages (en-US, zh-CN, etc.)
- **Automatic Punctuation**: Automatic punctuation in transcriptions
- **Single Utterance Mode**: Stop after detecting end of speech

### General Features
- **Health Checks**: Built-in health monitoring endpoints
- **Production Ready**: Comprehensive error handling, logging, and testing
- **Type Safe**: Full Pydantic schema validation

## 🏗️ Architecture

```
ai_chat/
├── api/                     # API layer
│   └── v1/
│       ├── __init__.py     # Router registration
│       ├── chat.py         # Chat endpoints
│       └── speech.py       # Speech-to-Text endpoints
├── models/                 # Data models
│   └── schemas.py          # Pydantic schemas
├── services/               # Business logic
│   ├── chat_service.py     # GenAI service implementation
│   └── speech_service.py   # Speech-to-Text service
├── examples/               # Example client scripts
│   └── speech_client_example.py
├── tests/                  # Unit tests
│   ├── test_config.py
│   ├── test_schemas.py
│   ├── test_chat_service.py
│   └── test_api.py
├── config.py              # Configuration management
├── deps.py                # Dependency injection
├── main.py                # FastAPI application
├── env.example            # Environment variables template
└── requirements.txt       # Python dependencies
```

## 📦 Prerequisites

- Python 3.8+
- Google Cloud Project with the following APIs enabled:
  - Vertex AI API (for chat)
  - Cloud Speech-to-Text API (for speech recognition)
- Google Cloud credentials configured (ADC or service account)
- Required IAM roles:
  - `Vertex AI User`
  - `AI Platform User`
  - `Cloud Speech Client` (for Speech-to-Text)
- For microphone transcription:
  - PyAudio compatible audio input device
  - PortAudio library (required by PyAudio)

## 🚀 Quick Start

### 1. Enable Required APIs

Visit the Google Cloud Console and enable the following APIs for your project:
- [Vertex AI API](https://console.cloud.google.com/apis/library/aiplatform.googleapis.com) (for chat)
- [Cloud Speech-to-Text API](https://console.cloud.google.com/apis/library/speech.googleapis.com) (for speech recognition)

### 2. Set Up Authentication

For local development:
```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

For production (service account):

**Windows PowerShell:**
```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS="C:\path\to\service-account-key.json"
```

**Windows CMD:**
```cmd
set GOOGLE_APPLICATION_CREDENTIALS=C:\path\to\service-account-key.json
```

**Linux/Mac:**
```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

### 3. Install Dependencies

**Install Python packages:**
```bash
cd ai_chat
pip install -r requirements.txt
```

**For Speech-to-Text (PyAudio may need system libraries):**

**Windows:**
```powershell
pip install pipwin
pipwin install pyaudio
```

**macOS:**
```bash
brew install portaudio
pip install pyaudio
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install portaudio19-dev python3-pyaudio
pip install pyaudio
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```bash
# Required for Chat
GOOGLE_GENAI_USE_VERTEXAI=True
GOOGLE_CLOUD_PROJECT=YOUR_PROJECT
GOOGLE_CLOUD_LOCATION=us-central1

# Optional - Chat Configuration
GENAI_MODEL=gemini-2.5-flash
GENAI_TEMPERATURE=0.7

# Optional - Speech-to-Text Configuration
SPEECH_LANGUAGE_CODE=en-US
SPEECH_SAMPLE_RATE=16000
SPEECH_ENABLE_AUTOMATIC_PUNCTUATION=True
```

**Setting Environment Variables:**

**Windows PowerShell:**
```powershell
$env:GOOGLE_CLOUD_PROJECT="YOUR_PROJECT"
$env:GOOGLE_CLOUD_LOCATION="us-central1"
$env:GOOGLE_GENAI_USE_VERTEXAI="True"
```

**Windows CMD:**
```cmd
set GOOGLE_CLOUD_PROJECT=YOUR_PROJECT
set GOOGLE_CLOUD_LOCATION=us-central1
set GOOGLE_GENAI_USE_VERTEXAI=True
```

**Linux/Mac:**
```bash
export GOOGLE_CLOUD_PROJECT=YOUR_PROJECT
export GOOGLE_CLOUD_LOCATION=us-central1
export GOOGLE_GENAI_USE_VERTEXAI=True
```

**Or use .env file (recommended):**
```bash
cp ai_chat/env.example .env
# Edit .env with your values - python-dotenv will load automatically
```

### 5. Run the Service

From the project root directory:

```bash
# Using Python module
python -m ai_chat.main

# Or using uvicorn directly
uvicorn ai_chat.main:app --reload --host 0.0.0.0 --port 8000
```

Access the API documentation at [http://localhost:8000/docs](http://localhost:8000/docs)

### 6. Try the Interactive Demo 🎤

**Browser-based Speech-to-Text Demo:**

Visit [http://localhost:8000/demo](http://localhost:8000/demo) in your browser to try the real-time speech transcription with your microphone!

Features:
- 🎙️ Real-time transcription from your browser microphone
- 🌍 Multiple language support (English, Chinese, Japanese, Korean, Spanish, French)
- 📊 Live confidence scores
- ✨ Beautiful, responsive UI

No additional setup required - just allow microphone access when prompted!

## ⚙️ Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_GENAI_USE_VERTEXAI` | Yes | `True` | Enable Vertex AI mode |
| `GOOGLE_CLOUD_PROJECT` | Yes | - | Your GCP project ID |
| `GOOGLE_CLOUD_LOCATION` | No | `us-central1` | GCP region |
| `GENAI_MODEL` | No | `gemini-2.5-flash` | Model to use |
| `GENAI_TEMPERATURE` | No | `0.7` | Generation temperature (0.0-2.0) |
| `GENAI_TOP_P` | No | `0.95` | Top-p sampling parameter |
| `GENAI_TOP_K` | No | `40` | Top-k sampling parameter |
| `GENAI_MAX_OUTPUT_TOKENS` | No | `8192` | Maximum output tokens |

### Available Models

- **gemini-2.5-flash** - Fast and efficient (recommended)
- **gemini-2.5-pro** - Most capable for complex tasks
- **gemini-2.0-flash-001** - Previous generation

See [Google Cloud documentation](https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models) for full model list.

### Temperature Guide

- **0.0-0.3**: Deterministic, factual (technical docs, code)
- **0.4-0.7**: Balanced (general chat, Q&A)
- **0.8-1.2**: Creative (writing, brainstorming)
- **1.3-2.0**: Highly random (experimental)

## 📚 API Documentation

### Health Check

**GET** `/health`

Check overall service health.

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "service": "AI Chat Service"
}
```

### Chat Service Health

**GET** `/api/v1/chat/health`

Check chat service and model status.

```bash
curl http://localhost:8000/api/v1/chat/health
```

Response:
```json
{
  "status": "healthy",
  "service": "Google Gen AI",
  "model": "gemini-2.5-flash"
}
```

### Chat (Non-Streaming)

**POST** `/api/v1/chat/`

Generate a complete response.

**Request:**
```json
{
  "message": "What is machine learning?",
  "history": [
    {
      "role": "user",
      "content": "Hello!"
    },
    {
      "role": "model",
      "content": "Hello! How can I help you today?"
    }
  ],
  "model": "gemini-2.5-flash",
  "temperature": 0.7,
  "max_tokens": 2048,
  "system_instruction": "You are a helpful AI assistant."
}
```

**Response:**
```json
{
  "message": "Machine learning is a subset of artificial intelligence...",
  "role": "model",
  "model_used": "gemini-2.5-flash",
  "usage": {
    "prompt_token_count": 25,
    "candidates_token_count": 150,
    "total_token_count": 175
  },
  "finish_reason": "STOP"
}
```

**Python Example:**
```python
import httpx
import asyncio

async def chat():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/chat/",
            json={
                "message": "Explain quantum computing",
                "temperature": 0.5
            }
        )
        result = response.json()
        print(result["message"])

asyncio.run(chat())
```

### Chat Stream (Streaming)

**POST** `/api/v1/chat/stream`

Generate a streaming response for real-time output.

**Request:**
```json
{
  "message": "Write a short story about AI",
  "temperature": 0.9,
  "system_instruction": "You are a creative writer."
}
```

**Python Example:**
```python
import httpx

with httpx.Client() as client:
    with client.stream(
        'POST',
        'http://localhost:8000/api/v1/chat/stream',
        json={"message": "Tell me a story"},
        timeout=30.0
    ) as response:
        for chunk in response.iter_text():
            print(chunk, end='', flush=True)
```

**JavaScript Example:**
```javascript
async function streamChat(message) {
  const response = await fetch('http://localhost:8000/api/v1/chat/stream', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({message})
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const {done, value} = await reader.read();
    if (done) break;
    
    const chunk = decoder.decode(value);
    console.log(chunk);
  }
}

streamChat("Tell me about the universe");
```

### Speech-to-Text Service Health

**GET** `/api/v1/speech/health`

Check speech-to-text service status.

```bash
curl http://localhost:8000/api/v1/speech/health
```

Response:
```json
{
  "status": "healthy",
  "service": "Google Cloud Speech-to-Text",
  "model": "en-US"
}
```

### Transcribe Audio File

**POST** `/api/v1/speech/transcribe`

Transcribe an audio file to text.

**Important:** Make sure the `sample_rate` parameter matches your audio file's actual sample rate. Mismatched sample rates will result in empty transcriptions.

**Parameters:**
- `file` (required): Audio file to transcribe (WAV, LINEAR16 format)
- `language_code` (optional): Language code (default: en-US)
- `sample_rate` (optional): Audio sample rate in Hz (default: 16000)
- `enable_automatic_punctuation` (optional): Enable automatic punctuation (default: true)

**Request (with 16kHz audio):**
```bash
curl -X POST "http://localhost:8000/api/v1/speech/transcribe?language_code=en-US" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@audio_16k.wav"
```

**Request (with 48kHz audio - specify sample_rate):**
```bash
curl -X POST "http://localhost:8000/api/v1/speech/transcribe?language_code=en-US&sample_rate=48000" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@audio.wav"
```

**Response:**
```json
{
  "transcript": "Hello, this is a test of speech recognition.",
  "confidence": 0.98,
  "language_code": "en-US",
  "sample_rate": 16000
}
```

**Python Example:**
```python
import requests

def transcribe_audio(file_path):
    with open(file_path, 'rb') as f:
        files = {'file': f}
        params = {'language_code': 'en-US'}
        response = requests.post(
            'http://localhost:8000/api/v1/speech/transcribe',
            files=files,
            params=params
        )
    return response.json()

result = transcribe_audio('audio.wav')
print(result['transcript'])
```

### Stream Microphone Transcription

**POST** `/api/v1/speech/stream/microphone`

Capture audio from the server's microphone and stream transcription results in real-time.

**Request:**
```json
{
  "language_code": "en-US",
  "duration_seconds": 10,
  "single_utterance": false
}
```

**Python Example:**
```python
import requests
import json

def stream_microphone():
    url = 'http://localhost:8000/api/v1/speech/stream/microphone'
    payload = {
        "language_code": "en-US",
        "duration_seconds": 10,
        "single_utterance": False
    }
    
    response = requests.post(url, json=payload, stream=True)
    
    for line in response.iter_lines():
        if line:
            result = json.loads(line.decode('utf-8'))
            is_final = result.get('is_final', False)
            transcript = result.get('transcript', '')
            
            if is_final:
                print(f"\nFinal: {transcript}")
                print(f"Confidence: {result.get('confidence', 'N/A')}")
            else:
                print(f"Interim: {transcript}", end='\r')

stream_microphone()
```

**Response Format** (Newline-delimited JSON):
```json
{"transcript": "hello", "is_final": false, "stability": 0.85}
{"transcript": "hello world", "is_final": false, "stability": 0.92}
{"transcript": "hello world", "is_final": true, "confidence": 0.96}
```

### Browser Microphone Real-time Transcription (WebSocket)

**🎤 Interactive Demo Page Available!**

Visit [http://localhost:8000/demo](http://localhost:8000/demo) or [http://localhost:8000/static/speech_demo.html](http://localhost:8000/static/speech_demo.html) to access the interactive web demo.

**WebSocket** `/api/v1/speech/stream/websocket`

Real-time audio streaming from browser microphone using WebSocket connection. This is the recommended method for web applications.

**Features:**
- ✅ Real-time transcription with interim results
- ✅ Low latency streaming
- ✅ Browser microphone support
- ✅ Multiple language support
- ✅ Automatic audio format conversion

**Parameters:**
- `language_code` (query, optional): Language code (default: en-US)
- `sample_rate` (query, optional): Audio sample rate in Hz (default: 16000)

**WebSocket Protocol:**

Client sends:
- Binary audio data (LINEAR16 PCM format, 16-bit, mono)
- Text message "close" to end the stream

Server sends:
- JSON messages with transcription results

**JavaScript Example:**
```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8000/api/v1/speech/stream/websocket?language_code=en-US&sample_rate=16000');

ws.onopen = () => {
    console.log('WebSocket connected');
    
    // Get microphone stream
    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            const audioContext = new AudioContext({ sampleRate: 16000 });
            const source = audioContext.createMediaStreamSource(stream);
            const processor = audioContext.createScriptProcessor(4096, 1, 1);
            
            processor.onaudioprocess = (e) => {
                // Convert Float32Array to Int16Array
                const float32 = e.inputBuffer.getChannelData(0);
                const int16 = new Int16Array(float32.length);
                for (let i = 0; i < float32.length; i++) {
                    const s = Math.max(-1, Math.min(1, float32[i]));
                    int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                }
                
                // Send audio data
                if (ws.readyState === WebSocket.OPEN) {
                    ws.send(int16.buffer);
                }
            };
            
            source.connect(processor);
            processor.connect(audioContext.destination);
        });
};

ws.onmessage = (event) => {
    const result = JSON.parse(event.data);
    console.log('Transcript:', result.transcript);
    console.log('Is final:', result.is_final);
    if (result.is_final) {
        console.log('Confidence:', result.confidence);
    }
};

// Close connection
ws.send('close');
ws.close();
```

**Response Format** (JSON messages):
```json
{"transcript": "hello", "is_final": false, "stability": 0.85}
{"transcript": "hello world", "is_final": false, "stability": 0.92}
{"transcript": "hello world", "is_final": true, "confidence": 0.96}
```

**Python WebSocket Client Example:**
```python
import asyncio
import websockets
import json
import pyaudio

async def stream_microphone():
    uri = "ws://localhost:8000/api/v1/speech/stream/websocket?language_code=en-US&sample_rate=16000"
    
    async with websockets.connect(uri) as websocket:
        print("Connected to WebSocket")
        
        # Setup audio
        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024
        )
        
        async def send_audio():
            try:
                while True:
                    data = stream.read(1024, exception_on_overflow=False)
                    await websocket.send(data)
                    await asyncio.sleep(0.01)
            except KeyboardInterrupt:
                await websocket.send("close")
        
        async def receive_transcripts():
            try:
                while True:
                    response = await websocket.recv()
                    result = json.loads(response)
                    if result['is_final']:
                        print(f"\nFinal: {result['transcript']}")
                        print(f"Confidence: {result.get('confidence', 'N/A')}")
                    else:
                        print(f"\rInterim: {result['transcript']}", end='')
            except websockets.exceptions.ConnectionClosed:
                print("\nConnection closed")
        
        # Run both tasks
        await asyncio.gather(send_audio(), receive_transcripts())

asyncio.run(stream_microphone())
```

### Stream Audio File Transcription

**POST** `/api/v1/speech/stream/upload`

Upload an audio file and stream transcription results with interim and final outputs.

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/speech/stream/upload?language_code=en-US" \
  -H "accept: application/x-ndjson" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@audio.wav"
```

**Python Example:**
```python
import requests
import json

def stream_audio_file(file_path):
    url = 'http://localhost:8000/api/v1/speech/stream/upload'
    
    with open(file_path, 'rb') as f:
        files = {'file': f}
        params = {'language_code': 'en-US'}
        response = requests.post(url, files=files, params=params, stream=True)
    
    for line in response.iter_lines():
        if line:
            result = json.loads(line.decode('utf-8'))
            print(f"[{'FINAL' if result['is_final'] else 'interim'}] {result['transcript']}")

stream_audio_file('audio.wav')
```

### Speech-to-Text Configuration

Configure speech recognition via environment variables in `.env`:

```bash
# Language code (en-US, zh-CN, ja-JP, etc.)
SPEECH_LANGUAGE_CODE=en-US

# Audio sample rate in Hz
SPEECH_SAMPLE_RATE=16000

# Recognition model
SPEECH_MODEL=default

# Enable automatic punctuation
SPEECH_ENABLE_AUTOMATIC_PUNCTUATION=True

# Single utterance mode
SPEECH_SINGLE_UTTERANCE=False
```

**Supported Languages:**
- `en-US` - English (United States)
- `zh-CN` - Chinese (Simplified, China)
- `zh-TW` - Chinese (Traditional, Taiwan)
- `ja-JP` - Japanese
- `es-ES` - Spanish (Spain)
- `fr-FR` - French
- `de-DE` - German
- [Full list of supported languages](https://cloud.google.com/speech-to-text/docs/languages)

**Audio Format Requirements:**
- Encoding: LINEAR16 (16-bit PCM WAV)
- Sample Rate: 16000 Hz (recommended)
- Channels: Mono (1 channel)
- File Size: Max 10 MB per streaming request

### Example Client Script

A complete example client is provided in `examples/speech_client_example.py`:

```bash
# Check service health
python ai_chat/examples/speech_client_example.py

# Transcribe an audio file
python ai_chat/examples/speech_client_example.py audio.wav
```

## 🧪 Testing

The service includes comprehensive unit tests covering configuration, schemas, service logic, and API endpoints.

### Run Tests

```bash
# Run all tests
pytest ai_chat/tests/

# Run with coverage
pytest ai_chat/tests/ --cov=ai_chat --cov-report=html

# Run specific test file
pytest ai_chat/tests/test_config.py -v

# Run specific test
pytest ai_chat/tests/test_api.py::TestChatEndpoint::test_chat_simple_message -v
```

### Test Structure

- `test_config.py` - Configuration validation and environment variable handling
- `test_schemas.py` - Pydantic model validation
- `test_chat_service.py` - Service logic and GenAI client interaction
- `test_api.py` - API endpoint behavior and error handling

### Mock Testing

Tests use mocks to avoid making actual API calls:

```python
@patch('ai_chat.services.chat_service.genai.Client')
def test_generate_response(mock_client_class):
    # Test without calling real API
    mock_client = Mock()
    mock_client_class.return_value = mock_client
    # ... test logic
```

## 🚢 Deployment

### Docker Deployment

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY ai_chat/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY ai_chat/ ./ai_chat/

# Set environment variables
ENV GOOGLE_GENAI_USE_VERTEXAI=True
ENV GOOGLE_CLOUD_PROJECT=your-project-id
ENV GOOGLE_CLOUD_LOCATION=us-central1

EXPOSE 8000

CMD ["uvicorn", "ai_chat.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:
```bash
docker build -t ai-chat-service .
docker run -p 8000:8000 \
  -e GOOGLE_CLOUD_PROJECT=your-project-id \
  -e GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json \
  ai-chat-service
```

### Google Cloud Run

```bash
# Build and deploy
gcloud run deploy ai-chat-service \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_GENAI_USE_VERTEXAI=True,GOOGLE_CLOUD_LOCATION=us-central1
```

Make sure the Cloud Run service account has:
- `Vertex AI User` role
- `AI Platform User` role

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-chat-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ai-chat-service
  template:
    metadata:
      labels:
        app: ai-chat-service
    spec:
      containers:
      - name: ai-chat
        image: gcr.io/your-project/ai-chat-service:latest
        env:
        - name: GOOGLE_GENAI_USE_VERTEXAI
          value: "True"
        - name: GOOGLE_CLOUD_PROJECT
          value: "your-project-id"
        - name: GOOGLE_CLOUD_LOCATION
          value: "us-central1"
        ports:
        - containerPort: 8000
```

## 🔧 Troubleshooting

### Issue: "Configuration validation failed"

**Error:**
```
Configuration validation failed:
  - GOOGLE_CLOUD_PROJECT environment variable is required
```

**Solution:**

**Windows PowerShell:**
```powershell
# Check current values
echo $env:GOOGLE_CLOUD_PROJECT
echo $env:GOOGLE_CLOUD_LOCATION

# Set if missing
$env:GOOGLE_CLOUD_PROJECT="YOUR_PROJECT"
$env:GOOGLE_CLOUD_LOCATION="us-central1"
$env:GOOGLE_GENAI_USE_VERTEXAI="True"
```

**Windows CMD:**
```cmd
# Check current values
echo %GOOGLE_CLOUD_PROJECT%
echo %GOOGLE_CLOUD_LOCATION%

# Set if missing
set GOOGLE_CLOUD_PROJECT=YOUR_PROJECT
set GOOGLE_CLOUD_LOCATION=us-central1
set GOOGLE_GENAI_USE_VERTEXAI=True
```

**Linux/Mac:**
```bash
# Check current values
echo $GOOGLE_CLOUD_PROJECT
echo $GOOGLE_CLOUD_LOCATION

# Set if missing
export GOOGLE_CLOUD_PROJECT=YOUR_PROJECT
export GOOGLE_CLOUD_LOCATION=us-central1
export GOOGLE_GENAI_USE_VERTEXAI=True
```

### Issue: "Could not automatically determine credentials"

**Solution:**

For local development:
```bash
gcloud auth application-default login
```

For production:
```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

Verify credentials:
```bash
gcloud auth list
gcloud config get-value project
```

### Issue: "403 Permission denied"

**Solution:**

Ensure your account/service account has required IAM roles:

```bash
# Grant Vertex AI User role
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="user:EMAIL" \
  --role="roles/aiplatform.user"

# Grant AI Platform User role  
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="user:EMAIL" \
  --role="roles/ml.developer"
```

### Issue: "Vertex AI API is not enabled"

**Solution:**

Enable the API:
```bash
gcloud services enable aiplatform.googleapis.com --project=PROJECT_ID
```

Or visit: https://console.cloud.google.com/apis/library/aiplatform.googleapis.com

### Issue: Port already in use

**Error:**
```
[Errno 98] Address already in use
```

**Solution:**
```bash
# Use a different port
uvicorn ai_chat.main:app --port 8001

# Or kill the process using port 8000
# Linux/Mac:
lsof -ti:8000 | xargs kill -9
# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### Debug Mode

Enable detailed logging:

```python
import logging
logging.getLogger('ai_chat').setLevel(logging.DEBUG)
```

Or run with debug flag:
```bash
uvicorn ai_chat.main:app --reload --log-level debug
```

## 📖 Additional Resources

- [Google Cloud Vertex AI Documentation](https://cloud.google.com/vertex-ai/generative-ai/docs/start/quickstart)
- [Gemini API Reference](https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/gemini)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)

## 🤝 Integration Example

Integrate into your main application:

```python
# app/main.py
from fastapi import FastAPI
from ai_chat.api.v1 import router as ai_chat_router

app = FastAPI(title="My Application")

# Include AI chat routes
app.include_router(ai_chat_router, prefix="/api")

# Your other routes...
```

## 📝 License

This project follows the main repository's license.

## 🔗 Quick Reference

### Essential Commands

**Windows:**
```powershell
# Setup
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r ai_chat/requirements.txt

# Run
python -m ai_chat.main

# Test
pytest ai_chat/tests/ -v
```

**Linux/Mac:**
```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install -r ai_chat/requirements.txt

# Run
python -m ai_chat.main

# Test
pytest ai_chat/tests/ -v
```

### Key URLs

- API Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc  
- Health Check: http://localhost:8000/health
- Chat Health: http://localhost:8000/api/v1/chat/health

---

**Need help?** Check the logs, run tests, or refer to the troubleshooting section above.
