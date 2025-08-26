# Response for Issue #9029: macOS M1 Desktop App Not Loading

Hi @ebuka-odih,

Thank you for reporting this issue with the Langflow Desktop app on macOS M1.

## Solutions to Try

**1. Fresh Installation**
Try reinstalling the desktop app:

1. Completely uninstall the current Langflow Desktop app
2. Download the latest version from [Langflow Desktop](https://www.langflow.org/desktop)
3. Install and launch the app
4. If macOS blocks the app, go to System Preferences > Security & Privacy and click "Open Anyway"

**2. If the Issue Persists**
To help diagnose the issue, please check for log files at one of these locations:
```
~/Library/Logs/Langflow/
~/Library/Logs/com.Langflow/
```

To access these folders:
- Open Finder
- Press `Cmd + Shift + G`
- Enter the path above
- Look for any `.log` files

**3. Alternative Installation Method**
As a workaround, you can install Langflow via pip:
```bash
pip install langflow
langflow run
```
Then access Langflow at `http://127.0.0.1:7860` in your browser.

## Additional Troubleshooting Steps

- **macOS Security**: On first launch, you may need to right-click the app and select "Open" to bypass Gatekeeper
- **Rosetta 2**: Ensure Rosetta 2 is installed (it should install automatically when needed)
- **System Requirements**: Confirm your macOS version is compatible with the desktop app

## Related Resources
- [Installation Guide](https://docs.langflow.org/get-started-installation)

Please let us know if these solutions work or if you continue to experience issues. If the problem persists, sharing any log files you find would be helpful for further diagnosis.

Best regards