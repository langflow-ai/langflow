# Chroma Vector Store retirement in langflow

Saved component `ext:chroma:ChromaVectorStoreComponent@official` is retired in the target contract. The compatibility identity remains available for inspection, while execution requires manual replacement.

Replace this saved node manually with a supported [Knowledge Base or remote vector store](https://docs.langflow.org/knowledge-storage-upgrade#replace-retired-components), migrate its data as needed, reconnect its edges, and test the flow. Keep the original flow and source data until validation succeeds.

Supported local Knowledge Base and Memory Base storage upgrades are separate from replacing standalone Chroma nodes. [Chroma Cloud requires administrator-led data migration](https://docs.langflow.org/troubleshoot#remote-source-requires-migration). Neither path automatically replaces this node. Installing the Chroma SDK does not re-enable the retired integration.

Release comparison `langflow` 1.13.2 to 1.14.0.

- Break identity `9f3165b479c2b03295d3f9814a6f58303607fe46672eef032a4c6fadaef7da9a`
- Break identity `9f3165b479c2b03295d3f9814a6f58303607fe46672eef032a4c6fadaef7da9a`
- Previous contract `71d4f962ecb49bd505c192cded435c737169a21692da37d8301acf9af3a333b7`
- Target contract `70bb4f4a726b4527d9ffa9b176cacf81d557f9f6412c49b594bc9cad3e911fb1`
