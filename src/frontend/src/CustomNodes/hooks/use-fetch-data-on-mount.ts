import { useEffect } from "react";
import type { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import type { APIClassType } from "@/types/api";
import useAlertStore from "../../stores/alertStore";
import { mutateTemplate } from "../helpers/mutate-template";

const useFetchDataOnMount = (
  node: APIClassType,
  nodeId: string,
  setNodeClass: (node: APIClassType) => void,
  name: string,
  postTemplateValue: ReturnType<typeof usePostTemplateValue>,
) => {
  const setErrorData = useAlertStore((state) => state.setErrorData);

  useEffect(() => {
    async function fetchData() {
      const template = node.template[name];
      if (!template) return;

      const tool = node.template.tool;
      // Refreshing a configured MCP server on mount can remove the saved
      // tool's argument fields and disconnect their edges.
      if (
        name === "mcp_server" &&
        template.type === "mcp" &&
        !node.tool_mode &&
        typeof tool?.value === "string" &&
        tool.value.length > 0 &&
        tool.options?.includes(tool.value)
      ) {
        return;
      }

      const isRealtimeOrRefresh =
        template.real_time_refresh ||
        template.refresh_button ||
        (node.tool_mode && name === "tools_metadata");

      const hasOptions = (template.options?.length ?? 0) > 0;
      const fieldSupportsOptions = template.options !== undefined;

      const needApiKeyPrefill =
        name === "model" &&
        node.template?.api_key != null &&
        !node.template?.api_key?.value;

      const shouldFetchOnMount =
        isRealtimeOrRefresh &&
        ((!hasOptions && fieldSupportsOptions) ||
          (!fieldSupportsOptions && !!template.value) ||
          (name === "api_key" && !template.value) ||
          needApiKeyPrefill);

      if (shouldFetchOnMount) {
        mutateTemplate(
          template.value,
          nodeId,
          node,
          setNodeClass,
          postTemplateValue,
          setErrorData,
          name,
          () => {},
          node.tool_mode,
        );
      }
    }
    fetchData();
  }, []);
};

export default useFetchDataOnMount;
