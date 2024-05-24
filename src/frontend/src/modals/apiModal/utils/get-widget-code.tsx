/**
 * Function to get the widget code for the API
 * @param {string} flow - The current flow.
 * @returns {string} - The widget code
 */
export default function getWidgetCode(
  flowId: string,
  flowName: string,
  isAuth: boolean,
): string {
  return `<script src="https://cdn.jsdelivr.net/gh/langflow-ai/langflow-embedded-chat@1.0_alpha/dist/build/static/js/bundle.min.js"></script>

  <langflow-chat
    window_title="${flowName}"
    flow_id="${flowId}"
    host_url="http://localhost:7860"${
      !isAuth
        ? `
    api_key="..."`
        : ""
    }

  ></langflow-chat>`;
}
