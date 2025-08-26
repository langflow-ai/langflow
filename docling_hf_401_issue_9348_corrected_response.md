# Docling HuggingFace 401 Error Issue #9348 - Corrected Response

Hi @ayush20501,

Thank you for reporting this issue with the Docling component and the 401 Unauthorized error.

## Root Cause Analysis (Verified)

The error `401 Client Error: Unauthorized for url: https://huggingface.co/api/models/ds4sd/docling-layout-old/revision/main` occurs when the **docling library** (not Langflow itself) attempts to download layout detection models from Hugging Face during initialization.

**Key Finding**: This model access happens **within the docling package**, not in Langflow code, making it a dependency issue rather than a Langflow bug.

## Related Issues (Confirmed)

This is part of a broader set of Docling stability issues:
- **Issue #9121**: "Docling - Network error" (similar model download problems)
- **Issue #9024**: "Docling build failed" (installation issues)

## Current Fix Status

**✅ PR #9393 MERGED**: "refactor(docling): extract processing logic to separate worker process"
- **Status**: Already included in current version
- **Impact**: Improves stability but may not directly address the 401 error
- **Benefit**: Better error isolation and handling

## Solutions to Try

### 1. **Set Hugging Face Authentication (Recommended)**

The most effective approach for resolving HF API issues:

```bash
# Option A: Environment variable
export HUGGINGFACE_HUB_TOKEN=your_token_here

# Option B: Using HF CLI
pip install huggingface_hub
huggingface-cli login
```

**Get token**: https://huggingface.co/settings/tokens

### 2. **Check Model Availability**

Verify the specific model is accessible:
```bash
# Test if the model endpoint is working
curl -H "Authorization: Bearer your_token" \
  "https://huggingface.co/api/models/ds4sd/docling-layout-old/revision/main"
```

### 3. **Network/Proxy Configuration**

If you're behind a corporate firewall:
```bash
export HTTP_PROXY=your_proxy
export HTTPS_PROXY=your_proxy
```

### 4. **Update Dependencies**

Ensure you have the latest docling version:
```bash
pip install --upgrade docling langflow[docling]
```

## Expected Resolution

Based on the pattern of issues:
1. **Authentication usually resolves** similar 401 errors
2. **Model endpoint might be temporarily unavailable**
3. **Network/proxy issues** are common in corporate environments

## Next Steps

1. **Try HF authentication first** (highest success probability)
2. **Check network connectivity** to huggingface.co
3. **Report back results** - this helps identify if it's a broader API issue
4. **Consider alternative docling configurations** if available

The refactored docling worker (PR #9393) should provide better error messages to help diagnose the specific cause.

**Current Status**: ⚠️ **Known Issue** - Multiple users affected, authentication typically resolves  
**Latest Version**: 1.5.0.post2 (includes docling stability fixes)  

Let me know if the authentication approach resolves the issue or if you need help with any of these steps.

Best regards,  
Langflow Support Team