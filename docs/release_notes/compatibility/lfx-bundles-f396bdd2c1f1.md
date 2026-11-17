# ALTK Agent retirement in lfx-bundles

Saved component `ext:altk:ALTKAgentComponent@official` is retired in the target contract. The compatibility identity remains available for inspection, while execution requires manual replacement.

Replace the saved ALTK node manually with the [Agent component](https://docs.langflow.org/components-agents). Reconfigure its model and tools from the retained settings, reconnect its edges, and test the flow. Review the former tool-validation and post-tool reflection requirements before enabling it. The Agent component does not automatically reproduce those ALTK behaviors.

Release comparison `lfx-bundles` 1.3.5 to 1.3.10.

- Break identity `f396bdd2c1f143135185b404a63bcf66d1bf185610e07817f9b3f7b7dbb2f954`
- Previous contract `b01738200e023dd642142dd5e9b4f18866a42057cc9043ffb0102d73265b8600`
- Target contract `7a2cf766b1ddc25ce32c1253fe0b4c5443e53eedd226d9cdd8b292ece9d414d5`
