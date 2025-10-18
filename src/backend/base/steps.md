# Complete Setup Guide: Running Langflow with PostgreSQL Database

## Prerequisites
- Python environment with langflow installed
- PostgreSQL database configured
- Frontend built with npm

## Step-by-Step Instructions

### 1. Environment Setup
Create a .env file in C:\Projects\langflow\langflow\.env with your PostgreSQL connection:
env
LANGFLOW_DATABASE_URL=postgresql://username:password@host:port/database_name


### 2. Build Frontend (if not already done)
bash
cd C:\Projects\langflow\langflow\src\frontend
npm install
npm run build

This creates the build directory with compiled React app.

### 3. Activate Virtual Environment
bash
cd C:\Projects\langflow
.venv\Scripts\activate


### 4. Navigate to Backend Directory
bash
cd C:\Projects\langflow\langflow\src\backend


### 5. Run Langflow Server
bash
uvicorn langflow.main_with_frontend:app --host 0.0.0.0 --port 7860 --reload --env-file "C:\Projects\langflow\langflow\.env"


### 6. Access Langflow
- *Main UI*: http://localhost:7860
- *API Docs*: http://localhost:7860/docs
- *Health Check*: http://localhost:7860/health

## What This Setup Does

1. *Uses Custom Wrapper*: The main_with_frontend.py file automatically locates your frontend build files in src/frontend/build
2. *Loads Environment*: Reads your PostgreSQL configuration from the .env file
3. *Serves Full Application*: Provides both the React frontend UI and the FastAPI backend
4. *Auto-reload*: Watches for code changes and automatically restarts the server

## Alternative Commands (if needed)

### Backend Only (API access only)
bash
cd C:\Projects\langflow\langflow\src\backend
uvicorn langflow.main_backend_only:app --host 0.0.0.0 --port 7860 --reload --env-file "C:\Projects\langflow\langflow\.env"


### Using Langflow CLI (if the wrapper doesn't work)
bash
cd C:\Projects\langflow\langflow
python -m langflow run --host 0.0.0.0 --port 7860 --frontend-path src/frontend/build --env-file .env


## Troubleshooting

### If you get "Static files directory does not exist" error:
- Ensure frontend is built: cd src/frontend && npm run build
- Check that src/frontend/build/ directory exists and contains index.html

### If you get database connection errors:
- Verify PostgreSQL is running
- Check your .env file has correct database credentials
- Test connection string format: postgresql://user:pass@host:port/dbname

### If port 7860 is in use:
- Change port number: --port 7861
- Or kill existing process using the port

## File Structure Reference

C:\Projects\langflow\
├── .venv/                          # Virtual environment
├── langflow/
│   ├── .env                        # Database configuration
│   ├── src/
│   │   ├── frontend/
│   │   │   ├── build/              # Built React app (npm run build)
│   │   │   │   ├── index.html
│   │   │   │   └── assets/
│   │   │   └── src/                # React source code
│   │   └── backend/
│   │       └── base/langflow/
│   │           ├── main_with_frontend.py  # Custom wrapper
│   │           └── main_backend_only.py   # Backend-only wrapper


## Quick Start Command (Copy-Paste Ready)
bash
cd C:\Projects\langflow && .venv\Scripts\activate && cd langflow\src\backend && uvicorn langflow.main_with_frontend:app --host 0.0.0.0 --port 7860 --reload --env-file "C:\Projects\langflow\langflow\.env"


Save this guide and you'll be able to run your Langflow setup consistently every time! 🚀