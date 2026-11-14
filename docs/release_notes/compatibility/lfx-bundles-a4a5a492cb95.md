# Local DB retirement in lfx-bundles

Saved component `ext:chroma:LocalDBComponent@official` is retired in the target contract. The compatibility identity remains available for inspection, while execution requires manual replacement.

Replace this saved node manually with a supported [Knowledge Base or remote vector store](https://docs.langflow.org/knowledge-storage-upgrade#replace-retired-components), migrate its data as needed, reconnect its edges, and test the flow. Keep the original flow and source data until validation succeeds.

Supported local Knowledge Base and Memory Base storage upgrades are separate from replacing standalone Chroma nodes. [Chroma Cloud requires administrator-led data migration](https://docs.langflow.org/troubleshoot#remote-source-requires-migration). Neither path automatically replaces this node. Installing the Chroma SDK does not re-enable the retired integration.

Release comparison `lfx-bundles` 1.3.5 to 1.3.9.

- Break identity `a4a5a492cb95a988f0e13f22909e50919e3a3854a422318924e6563266a0f5b3`
- Previous contract `02f2cf302bcd204b65e3e2aaac44c8f5d7c6dd63c7e800411f69cb3cf0e9ab55`
- Target contract `c5dec403563d038a2118640a7dc1c61ef9eda86e8a4cee8fe101bb4903fc0406`
