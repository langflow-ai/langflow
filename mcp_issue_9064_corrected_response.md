# Response for Issue #9064: MCP Server Process Leak

Hi @roudy16,

Thank you for this detailed bug report with excellent reproduction steps. You've identified a significant resource management issue in Langflow 1.5.0.post1.

## Issue Confirmation

Your observation is correct - MCP server processes in STDIO mode are not being cleaned up when the Flow editor is opened/closed, leading to process accumulation and eventual memory exhaustion.

## Root Cause Analysis

Based on the codebase analysis:
- Each Flow editor page load creates new MCP server subprocess instances
- The session management doesn't properly terminate STDIO subprocesses
- While there's a test file (`test_mcp_memory_leak.py`) that addresses this issue, it's currently skipped in the test suite
- Recent PRs (#8717, #8870, #8908) improved MCP error handling but didn't fully address STDIO cleanup

## Immediate Workarounds

### 1. **Switch to SSE Transport Using Supergateway (Recommended)**
Convert your STDIO MCP servers to SSE transport to avoid subprocess issues:

```bash
# Install supergateway
npm install -g supergateway

# Run your MCP server through supergateway
npx supergateway --port 8080 --stdio "npx -y @upstash/context7-mcp"

# Update your Langflow MCP config to use SSE
{
  "mcpServers": {
    "context7": {
      "url": "http://localhost:8080/sse"
    }
  }
}
```

**Supergateway**: https://github.com/supercorp-ai/supergateway

### 2. **Manual Process Cleanup**
Monitor and clean up orphaned processes:

```bash
# Count processes (as you're already doing)
ps -aux | grep 'npm exec @upstash/context7-mcp' | wc -l

# Clean up orphaned processes (use carefully)
pkill -f "@upstash/context7-mcp"
```

### 3. **Periodic Server Restart**
Restart Langflow periodically to clear accumulated processes:

```bash
# For local installation
pkill -f langflow && langflow run

# For Docker
docker restart <langflow-container>
```

## Additional Monitoring

Create a monitoring script to track process accumulation:

```bash
#!/bin/bash
while true; do
  count=$(ps -aux | grep 'npm exec @upstash/context7-mcp' | grep -v grep | wc -l)
  echo "$(date): MCP processes: $count"
  if [ $count -gt 10 ]; then
    echo "Warning: High process count detected!"
  fi
  sleep 60
done
```

## Next Steps

This issue requires a fix in the MCP session lifecycle management. The test infrastructure exists but needs to be enabled and the fix implemented. Until then, using SSE transport via supergateway is the most reliable workaround.

Please let me know if you need help setting up any of these workarounds.

Best regards,  
Langflow Support