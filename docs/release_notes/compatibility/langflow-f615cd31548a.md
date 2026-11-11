# ALTK Agent retirement in langflow

Saved component `ext:altk:ALTKAgentComponent@official` is retired in the target contract. The compatibility identity remains available for inspection, while execution requires manual replacement.

Replace the saved ALTK node manually with the [Agent component](https://docs.langflow.org/components-agents). Reconfigure its model and tools from the retained settings, reconnect its edges, and test the flow. Review the former tool-validation and post-tool reflection requirements before enabling it. The Agent component does not automatically reproduce those ALTK behaviors.

Release comparison `langflow` 1.13.2 to 1.14.0.

- Break identity `f615cd31548a8e3dd56428242fe4ed26ea858737919ad1ea5d5b6045755ff5db`
- Break identity `f615cd31548a8e3dd56428242fe4ed26ea858737919ad1ea5d5b6045755ff5db`
- Previous contract `784047b3a3ce9e40583c677f76b0690b38a9db6ec4ad4bf67386d62580254ece`
- Target contract `7a2cf766b1ddc25ce32c1253fe0b4c5443e53eedd226d9cdd8b292ece9d414d5`
