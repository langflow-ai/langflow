/**
 * Lifted-state payload shape emitted by connector forms in deferred mode.
 * Matches ``ConnectorIngestRequest`` minus ``kb_name`` / chunking fields
 * (those are owned by the parent — typically the create-KB modal — since
 * they apply to any source type, not just connectors).
 */
export interface DeferredConnectorPayload {
  source_type: string;
  source_config: Record<string, unknown>;
  source_name: string;
}
