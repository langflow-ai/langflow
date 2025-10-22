/// <reference types="vite/client" />
/// <reference types="vite-plugin-svgr/client" />

interface ImportMetaEnv {
  readonly BACKEND_URL: string;
  readonly ACCESS_TOKEN_EXPIRE_SECONDS: string;
  readonly CI: string;
  readonly LANGFLOW_AUTO_LOGIN: string;
  readonly LANGFLOW_MCP_COMPOSER_ENABLED: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module "*.svg" {
  const content: string;
  export default content;
}
