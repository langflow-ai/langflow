# ALTK Agent retirement in langflow

Saved component `ext:altk:ALTKAgentComponent@official` is retired in the target contract. The compatibility identity remains available for inspection, while execution requires manual replacement.

Replace the saved ALTK node manually with the [Agent component](https://docs.langflow.org/components-agents). Reconfigure its model and tools from the retained settings, reconnect its edges, and test the flow. Review the former tool-validation and post-tool reflection requirements before enabling it. The Agent component does not automatically reproduce those ALTK behaviors.

Release comparison `langflow` 1.13.2 to 1.14.0.

- Break identity `8e0c64bf4bc0e468b3b45aead5309d8ede4221fd400d9acec8dd3efd44030abb`
- Previous contract `784047b3a3ce9e40583c677f76b0690b38a9db6ec4ad4bf67386d62580254ece`
- Target contract `7a2cf766b1ddc25ce32c1253fe0b4c5443e53eedd226d9cdd8b292ece9d414d5`
