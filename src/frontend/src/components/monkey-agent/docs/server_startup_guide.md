# Starting the Langflow Server with Monkey Agent

This guide provides instructions for starting the Langflow server with the enhanced Monkey Agent registry implementation.

## Prerequisites

- Langflow repository cloned
- All dependencies installed

## Starting the Servers

Starting Langflow requires running both the backend and frontend servers. This can be done using the make commands provided in the project.

### Step 1: Start the Backend Server

```bash
cd /path/to/langflow-fork
make backend
```

This will start the backend server at http://localhost:7860.

### Step 2: Start the Frontend Server

In a new terminal window:

```bash
cd /path/to/langflow-fork
make frontend
```

This will start the frontend development server at http://localhost:3000.

### Step 3: Access the UI

Once both servers are running, you can access the Langflow UI by opening:

- http://localhost:3000 in your browser

## Testing the Enhanced Registry

The Monkey Agent enhanced registry exposes several API endpoints that can be tested directly:

- Registry overview: `http://localhost:7860/api/v1/monkey-agent/registry`
- Node details: `http://localhost:7860/api/v1/monkey-agent/registry/node/{node_id}`
- Compatibility matrix: `http://localhost:7860/api/v1/monkey-agent/registry/compatibility`
- Connection suggestions: `http://localhost:7860/api/v1/monkey-agent/connection/suggest`

## Troubleshooting

If you encounter issues starting the servers:

1. Ensure all dependencies are properly installed
2. Check for error messages in the terminal output
3. Verify that the ports (7860 for backend, 3000 for frontend) are available and not in use by other applications

## Configuration

You can customize the server startup by modifying parameters in the make commands:

```bash
# Custom port for backend
make backend port=8000

# Custom environment file
make backend env=.custom-env
```
