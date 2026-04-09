// Fields to hide per component type in the InspectionPanel.
// Add entries here to hide fields without removing backend functionality.
export const HIDDEN_FIELDS: Record<string, string[]> = {
  ChatInput: ["should_store_message", "sender"],
  ChatOutput: ["should_store_message", "sender", "data_template", "clean_data"],
  APIRequest: ["follow_redirects", "save_to_file", "include_httpx_metadata"],
  SQLComponent: ["include_columns", "add_error"],
  URLComponent: [
    "prevent_outside",
    "use_async",
    "filter_text_html",
    "continue_on_failure",
    "check_response_status",
    "autoset_encoding",
  ],
  UnifiedWebSearch: ["ceid"],
  Agent: ["format_instructions", "output_schema", "verbose"],
  EmbeddingModel: ["show_progress_bar", "chunk_size"],
  Memory: ["sender_type"],
  StructuredOutput: ["system_prompt", "schema_name"],
  KnowledgeBase: ["include_embeddings"],
  DynamicCreateData: ["include_metadata"],
  SplitText: ["keep_separator"],
  File: [
    "silent_errors",
    "delete_server_file_after_processing",
    "ignore_unsupported_extensions",
    "ignore_unspecified_files",
    "pipeline",
    "md_image_placeholder",
    "md_page_break_placeholder",
    "doc_key",
    "use_multithreading",
  ],
};

// Fields to show in the InspectionPanel but hide from the advanced settings edit mode.
// These fields are intentionally surfaced only in the InspectionPanel for a streamlined UX.
export const INSPECTION_PANEL_ONLY_FIELDS: Record<string, string[]> = {
  Agent: ["api_key"],
  EmbeddingModel: ["api_key"],
  LanguageModelComponent: ["api_key"],
  BatchRunComponent: ["api_key"],
  GuardrailValidator: ["api_key"],
  SmartRouter: ["api_key"],
  "Smart Transform": ["api_key"],
  StructuredOutput: ["api_key"],
  KnowledgeBase: ["api_key"],
};
