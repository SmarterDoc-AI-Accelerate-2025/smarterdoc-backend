# smarterdoc-backend

## Getting Started

You can run this application either locally using a Python virtual environment or, preferably, using Docker Compose for a quick, isolated setup that includes the necessary ElasticSearch dependency.

### Prerequisites

- Git

- Python 3.11+ (if running locally)

- Docker and Docker Compose (recommended setup)

### Setup with Docker Compose (Recommended)

This method builds the FastAPI application within a container and automatically spins up a local ElasticSearch instance, linking them together.

#### A. Clone the Repository

First, clone the backend folder and navigate into it:

```
git clone <repository_url>
cd backend
```

#### B. Configure Environment Variables

Create a local .env file based on the provided example. This file stores configuration secrets and connection strings.

```
cp .env.example .env
```

Note: Edit the new .env file to customize settings or add actual Twilio/Elastic API keys, but the default values should work for local development.

#### C. Spin Up the Services

Use Docker Compose to build the application image and start both the backend and elastic services.

```
docker compose up --build -d
```

#### D. Verify Status

The API should be available shortly after starting.

FastAPI Backend: Access the health check endpoint at `http://localhost:8080/healthz` (should return {"ok": true, ...}).

ElasticSearch: Accessible at `http://localhost:9200` (for debugging).

### Google Cloud
Backend Link: `https://smarterdoc-backend-1094971678787.us-central1.run.app/`
Test Endpoint: `https://smarterdoc-backend-1094971678787.us-central1.run.app/hello`
