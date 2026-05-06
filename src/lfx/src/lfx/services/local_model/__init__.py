"""Bundled local-model service — detection, health, and (later) install orchestration.

This package backs the "Langflow Model" provider so Langflow works without any
third-party API key. Submodules:

  - platform_detection : "what platform am I on?" (no I/O beyond fs/env reads)
  - ollama_binary      : "is the Ollama CLI installed?" (subprocess + shutil.which)
  - ollama_health      : "is the Ollama server reachable?" (async HTTP probe)
"""
