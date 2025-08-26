# Response for Issue #8972: Vite Proxy Connection Error

Hi @zkProgrammer,

Thank you for reporting this Vite proxy error. I can see that your backend works fine with Postman but the frontend cannot connect. This is a common development environment issue related to IPv6/IPv4 localhost resolution.

## Analysis

The error `ECONNREFUSED ::1:7860` shows that Vite's proxy is trying to connect to IPv6 localhost (`::1`) but cannot reach your backend on port 7860. Since Postman works, your backend is running, but there's a connection issue between the frontend and backend.

## Solution Steps

### 1. First, verify your backend is actually running on port 7860:
```bash
# Check if something is listening on port 7860
lsof -i :7860
# or
netstat -tlnp | grep 7860
```

### 2. Ensure both backend and frontend are started properly:
```bash
# Terminal 1: Start backend (should listen on 7860)
make backend
# or directly with
langflow run --host 0.0.0.0 --port 7860

# Terminal 2: Start frontend development server (should listen on 3000 and proxy to 7860)  
cd src/frontend && npm run dev
```

### 3. Force IPv4 localhost in your Vite configuration:

Edit `src/frontend/vite.config.mts` line 26 and modify the target to use IPv4:
```typescript
const target =
  env.VITE_PROXY_TARGET || PROXY_TARGET || "http://127.0.0.1:7860";
```

### 4. Alternative: Set environment variable to force IPv4:
```bash
# Before starting frontend
export VITE_PROXY_TARGET=http://127.0.0.1:7860
cd src/frontend && npm run dev
```

### 5. If still having issues, bind backend to all interfaces:
When starting Langflow backend, use:
```bash
langflow run --host 0.0.0.0 --port 7860
```

## Root Cause Explanation

Your system is trying to connect via IPv6 (`::1`) but the backend is likely only listening on IPv4 (`127.0.0.1`). This is a common issue on systems with dual-stack networking.

## Quick Test

To confirm this is the issue, try:
```bash
# Test IPv4
curl http://127.0.0.1:7860/health

# Test IPv6  
curl http://[::1]:7860/health
```

If IPv4 works but IPv6 doesn't, the solutions above will fix your problem.

Let me know if you need further assistance!

## Additional Resources

- [Langflow Installation Guide](https://docs.langflow.org/get-started-installation)
- [Development Environment Setup](https://docs.langflow.org/contributing-how-to-contribute#-development-environment)

Best regards,  
Langflow Support

---

## 注意 (Note)

如果您需要中文支持，请告诉我，我可以用中文提供详细说明。
(If you need support in Chinese, please let me know and I can provide detailed instructions in Chinese.)