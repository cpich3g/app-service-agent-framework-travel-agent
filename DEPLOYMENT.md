# Python FastAPI Deployment Guide

This guide explains how to run and deploy the Python/FastAPI version of the Travel Planner application.

## Local Development

### Prerequisites
- Python 3.11 or higher
- pip (Python package manager)
- Azure account with required services (for full functionality)

### Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment variables:**
   
   Copy `.env.example` to `.env` and fill in the values:
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` with your Azure service details:
   - Service Bus namespace or connection string
   - Cosmos DB endpoint
   - Azure OpenAI endpoint
   - Other configuration as needed

3. **Run the application:**
   
   **Option 1: Using the main.py script (recommended)**
   ```bash
   python main.py
   ```
   This starts both the FastAPI server and the background worker in a single process.
   
   **Option 2: Run API and worker separately**
   
   Terminal 1 (API server):
   ```bash
   cd src
   uvicorn travel_planner.api.main:app --reload --port 8000
   ```
   
   Terminal 2 (Background worker):
   ```bash
   python -m travel_planner.services.worker
   ```

4. **Access the application:**
   - Web UI: http://localhost:8000
   - API Documentation: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health

## Testing

Run the basic verification tests:
```bash
python test_conversion.py
```

## Deployment to Azure App Service

### Using Azure Developer CLI (azd)

1. **Login to Azure:**
   ```bash
   azd auth login
   ```

2. **Deploy:**
   ```bash
   azd up
   ```
   
   This will:
   - Create all required Azure resources
   - Deploy the Python application
   - Configure environment variables
   - Set up managed identity authentication

### Manual Deployment

If you prefer manual deployment:

1. **Create an Azure App Service with Python runtime:**
   ```bash
   az webapp create \
     --resource-group <your-rg> \
     --plan <your-plan> \
     --name <your-app-name> \
     --runtime "PYTHON:3.11"
   ```

2. **Configure startup command:**
   ```bash
   az webapp config set \
     --resource-group <your-rg> \
     --name <your-app-name> \
     --startup-file "startup.sh"
   ```

3. **Set environment variables:**
   ```bash
   az webapp config appsettings set \
     --resource-group <your-rg> \
     --name <your-app-name> \
     --settings \
       SERVICE_BUS_NAMESPACE="<your-namespace>" \
       COSMOS_DB_ENDPOINT="<your-endpoint>" \
       AGENT_AZURE_OPENAI_ENDPOINT="<your-openai-endpoint>" \
       # ... other settings
   ```

4. **Deploy code:**
   ```bash
   az webapp deploy \
     --resource-group <your-rg> \
     --name <your-app-name> \
     --src-path . \
     --type zip
   ```

## Architecture

The Python application maintains the same architecture as the C# version:

- **FastAPI** - Modern Python web framework (equivalent to ASP.NET Core)
- **Pydantic** - Data validation and serialization (equivalent to C# models)
- **Azure SDK for Python** - Azure service integration
- **asyncio** - Asynchronous programming support
- **Background Worker** - Processes Service Bus messages

### Key Components

1. **`src/travel_planner/api/main.py`** - FastAPI application with endpoints
2. **`src/travel_planner/services/travel_plan_service.py`** - Handles travel plan requests
3. **`src/travel_planner/services/travel_agent_service.py`** - AI agent service
4. **`src/travel_planner/services/worker.py`** - Background worker for async processing
5. **`src/travel_planner/shared/models.py`** - Pydantic data models
6. **`main.py`** - Entry point that runs both API and worker

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `APP_BASE_URL` | Base URL of the application | No (default: http://localhost:8000) |
| `SERVICE_BUS_NAMESPACE` | Service Bus namespace (for managed identity) | Yes* |
| `SERVICE_BUS_CONNECTION_STRING` | Service Bus connection string (for local dev) | Yes* |
| `SERVICE_BUS_QUEUE_NAME` | Queue name | No (default: travel-plans) |
| `COSMOS_DB_ENDPOINT` | Cosmos DB endpoint URL | Yes |
| `COSMOS_DB_DATABASE_NAME` | Database name | No (default: TravelPlanner) |
| `COSMOS_DB_CONTAINER_NAME` | Container name | No (default: travel-plans) |
| `AGENT_AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint | Yes |
| `AGENT_MODEL_DEPLOYMENT_NAME` | Model deployment name | No (default: gpt-4o) |
| `LOG_LEVEL` | Logging level | No (default: INFO) |

*Either namespace (with managed identity) or connection string is required

## Key Differences from C# Version

### Similarities
- Same API endpoints and response models
- Same asynchronous request-reply pattern
- Same Azure services (Service Bus, Cosmos DB, Azure OpenAI)
- Same business logic and functionality
- Same static web UI

### Framework Equivalents
- **ASP.NET Core** → **FastAPI**
- **C# Models** → **Pydantic Models**
- **Hosted Service** → **Background asyncio task**
- **Dependency Injection** → **FastAPI lifespan + global service**
- **Azure SDKs for .NET** → **Azure SDKs for Python**

### Code Organization
- `TravelPlanner.Api` → `travel_planner/api`
- `TravelPlanner.Shared` → `travel_planner/shared`
- `Services/` → `services/`
- `.csproj` → `requirements.txt`
- `Program.cs` → `api/main.py`

## Troubleshooting

### Import Errors
Make sure you're running from the project root directory and that `src` is in the Python path.

### Azure SDK Authentication Issues
Ensure you have:
- Proper environment variables set
- Managed identity configured (for Azure deployment)
- Appropriate RBAC roles assigned

### Worker Not Processing Messages
Check:
1. Service Bus queue exists and has messages
2. Worker is running (check logs)
3. Managed identity has proper permissions
4. Connection configuration is correct

### Dependencies Installation Issues
Try upgrading pip:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Azure SDK for Python](https://docs.microsoft.com/python/azure/)
- [Azure App Service Python Deployment](https://docs.microsoft.com/azure/app-service/quickstart-python)
