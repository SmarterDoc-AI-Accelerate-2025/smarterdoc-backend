# smarterdoc-backend

## GCP Link

Backend Link: https://smarterdoc-backend-1094971678787.us-central1.run.app

Test End Point: https://smarterdoc-backend-1094971678787.us-central1.run.app/hello

## Getting Started

You can run this application either locally using a Python virtual environment or, preferably, using Docker Compose for a quick, isolated setup that includes the necessary dependencies.

### Prerequisites

- Git

- Python 3.11+ (if running locally)

- Docker and Docker Compose (recommended setup)

### Setup with Docker Compose (Recommended)

This method builds the FastAPI application within a container

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

Note: Edit the new .env file to customize settings or add actual Twilio and Fivetran API keys, but the default values should work for local development.

#### C. Spin Up the Services

Use Docker Compose to build the application image and start the backend service

```
docker compose up --build -d
```

#### D. Verify Status

The API should be available shortly after starting.

FastAPI Backend: Access the health check endpoint at `http://localhost:8080/healthz` (should return {"ok": true, ...}).

## Development Setup

```bash
# Install production dependencies
pip install -r requirements.txt

# Install development dependencies (for local audio recording)
pip install -r requirements-dev.txt
```

---

## NPI Data Extraction Tools

This repository also includes advanced tools for extracting healthcare provider data from the NPI Registry.

**Location**: [`npi_tools/`](./npi_tools/)

**Features**:

- **Multi-level Sharding**: Break through the 1200-record API limit
- **Complete Data**: Extract all healthcare providers for any city
- **Smart Analysis**: Analyze specialty distribution

**Quick Start**:

```bash
cd npi_tools
python NPI_multilevel_shard.py "New York" "NY"
```

**Results**: Successfully extracted 73,581+ NPI records for New York City (7x improvement over traditional methods)

📖 **[Full Documentation](./npi_tools/README.md)**

### Data Disclaimer

This project uses publicly available information about medical professionals (e.g., names, specialties, and practice locations) strictly for demonstration and educational purposes during the AI-Accelerate Hackathon.
All profile photos or biographical data are sourced from public stock photos and not actual doctors photos.
Any data will be deleted after the hackathon ends.
