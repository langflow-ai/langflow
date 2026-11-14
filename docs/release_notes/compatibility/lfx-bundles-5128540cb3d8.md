# Chroma Vector Store retirement in lfx-bundles

Saved component `ext:chroma:ChromaVectorStoreComponent@official` is retired in the target contract. The compatibility identity remains available for inspection, while execution requires manual replacement.

Replace this saved node manually with a supported [Knowledge Base or remote vector store](https://docs.langflow.org/knowledge-storage-upgrade#replace-retired-components), migrate its data as needed, reconnect its edges, and test the flow. Keep the original flow and source data until validation succeeds.

Supported local Knowledge Base and Memory Base storage upgrades are separate from replacing standalone Chroma nodes. [Chroma Cloud requires administrator-led data migration](https://docs.langflow.org/troubleshoot#remote-source-requires-migration). Neither path automatically replaces this node. Installing the Chroma SDK does not re-enable the retired integration.

Release comparison `lfx-bundles` 1.3.5 to 1.3.8.

- Break identity `5128540cb3d86313123f3dff8243d6a8e726af25f5bbc2c2ff64e83dbd1d3bbf`
- Previous contract `71d4f962ecb49bd505c192cded435c737169a21692da37d8301acf9af3a333b7`
- Target contract `70bb4f4a726b4527d9ffa9b176cacf81d557f9f6412c49b594bc9cad3e911fb1`
