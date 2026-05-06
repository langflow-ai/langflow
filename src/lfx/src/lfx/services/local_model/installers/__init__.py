"""Per-OS Ollama installers.

Each installer implements the Installer protocol (see protocol.py) and is selected
by `installer_factory.get_installer()` based on the detected platform.
"""
