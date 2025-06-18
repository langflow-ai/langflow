import { customGetHostProtocol } from "@/customization/utils/custom-get-host-protocol";
import { GetCodeType } from "@/types/tweaks";

/**
 * Function to get the widget code for the API
 * @param {string} flow - The current flow.
 * @returns {string} - The widget code
 */
export default function getWidgetCode({
  flowId,
  flowName,
  isAuth,
  copy = false,
}: GetCodeType): string {
  const source = copy
    ? `<script
  src="https://cdn.jsdelivr.net/gh/logspace-ai/langflow-embedded-chat@v1.0.7/dist/build/static/js/bundle.min.js">
</script>`
    : `<script
  src="https://cdn.jsdelivr.net/gh/logspace-ai/langflow-embedded-chat@v1.0.7/dist/
build/static/js/bundle.min.js">
</script>`;

  const { protocol, host } = customGetHostProtocol();

  return `${source}
  <langflow-chat
    window_title="${flowName}"
    flow_id="${flowId}"
    host_url="${protocol}//${host}"${
      !isAuth
        ? `
    api_key="..."`
        : ""
    }>
</langflow-chat>`;
}
