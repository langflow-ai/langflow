# SDK project ZIP uploads

The sync and async SDK `upload_project(zip_bytes)` methods now send a multipart `file` part, as required by the project upload API. ZIP bytes are unchanged. The filename is `project.zip`, so the server names the imported project `project` and applies its existing name-uniqueness rules.

HTTPX generates the multipart boundary. The SDK sets it on this request only, preserving shared client headers, authentication, error mapping and client ownership. Empty and invalid archives still reach server validation. There is no new dependency or public parameter.

Validation uses the complete SDK target with the repository's root workspace composition (`UV_PROJECT` set to the checkout root). The SDK-only bare target has three existing missing-LFX failures in CLI tests. Package builds run without `UV_PROJECT` so they build `langflow-sdk`, not the root distribution. Real application checks use a disposable SQLite database, actual authentication, native HTTPX sync/async clients and persisted-flow reads.
