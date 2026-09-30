export const ENABLE_DARK_MODE = true;
export const ENABLE_API = true;
export const ENABLE_LANGFLOW_STORE = false;
export const ENABLE_PROFILE_ICONS = true;
export const ENABLE_SOCIAL_LINKS = true;
export const ENABLE_BRANDING = true;
export const ENABLE_MVPS = false;
export const ENABLE_CUSTOM_PARAM = false;
export const ENABLE_INTEGRATIONS = false;
export const ENABLE_DATASTAX_LANGFLOW = false;
export const ENABLE_FILE_MANAGEMENT = true;
export const ENABLE_PUBLISH = true;
export const ENABLE_WIDGET = true;
export const ENABLE_VOICE_ASSISTANT = true;
export const ENABLE_FILES_ON_PLAYGROUND = true;
export const ENABLE_MCP = true;
export const ENABLE_MCP_NOTICE = false;
export const ENABLE_KNOWLEDGE_BASES = true;
export const ENABLE_INSPECTION_PANEL = true;

export const ENABLE_MCP_COMPOSER =
  import.meta.env.LANGFLOW_MCP_COMPOSER_ENABLED === "true";
export const ENABLE_NEW_SIDEBAR = true;
export const ENABLE_FETCH_CREDENTIALS = false;
// Mode A only: gates the Bundle-header Reload action in the palette.  Off by
// default until the bundle-list endpoint that populates extension_id per
// bundle ships; until then the static SIDEBAR_BUNDLES has no reliable
// extension id to send to /api/v1/extensions/{id}/bundles/{name}/reload.
export const ENABLE_EXTENSION_RELOAD =
  import.meta.env.LANGFLOW_EXTENSION_RELOAD_ENABLED === "true";
