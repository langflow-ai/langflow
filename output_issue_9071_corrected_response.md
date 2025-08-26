# Response for Issue #9071: Output Disconnection

Hi @fortuneray,

Thank you for reporting this issue with multiple outputs disconnecting. This is a confirmed bug affecting several users, and I understand how disruptive this is to your workflow.

## Issue Confirmation

You're experiencing a **known bug** where components with multiple outputs lose their connections after execution. This is not just a visual issue - the connections are actually being removed.

## Root Cause

According to the codebase analysis and dosubot's investigation:
- Langflow validates output connections against the exact signature (name, type, order) of each output
- If **any** aspect of the output signature changes between runs, connections are invalidated and removed
- This particularly affects the second and subsequent outputs, while the first output often survives

## Affected Components

Based on user reports and the collaborator's response:
- **Custom components** with multiple outputs (your case)
- **SQLAgent** (confirmed by @lice-reis)
- **Tool Calling Agent** (possibly affected)
- Components that dynamically change output signatures

## Immediate Workarounds

### 1. **Use Core Components (Recommended by Team)**
As @lice-reis (Langflow collaborator) suggests:
- Switch to the **Agent component** instead of Tool Calling Agent
- Core components are more stable and actively maintained
- The Agent component can handle tool calls directly

### 2. **Ensure Stable Output Signatures**
For custom components:
- Keep output definitions (name, type, order) **exactly the same** between runs
- Avoid dynamic output generation
- Define all outputs upfront, even if not always used

### 3. **Single Output with Structured Data**
As you mentioned, consider:
- Combining multiple outputs into one structured output
- Using a single output with JSON/dictionary containing all data
- Parse the structured output downstream as needed

## Version Information

Please confirm your exact version by running:
```bash
langflow --version
```
(You mentioned "1.50" but current versions are like "1.5.0" or "1.5.0.post2")

## Next Steps

1. **Try the Agent component** as suggested by the Langflow team member
2. **Report specific component types** that are failing for you
3. **Consider upgrading** if you're not on the latest version

This is a legitimate bug that needs to be fixed in the core product. The team is aware, and using core components is the best workaround currently available.

Best regards,  
Langflow Support