import { useEffect } from "react";
import type { APIClassType } from "@/types/api";
import useAlertStore from "../../stores/alertStore";
import { mutateTemplate } from "../helpers/mutate-template";

const useFetchDataOnMount = (
  node: APIClassType,
  nodeId: string,
  setNodeClass: (node: APIClassType) => void,
  name: string,
  postTemplateValue: Parameters<typeof mutateTemplate>[4],
) => {
  const setErrorData = useAlertStore((state) => state.setErrorData);

  useEffect(() => {
    async function fetchData() {
      const template = node.template[name];
      if (!template) return;

      // A saved MCP selection already carries its generated inputs. Replaying
      // historical component code on mount can discard them before Update.
      const savedTool = node.template.tool;
      if (
        template._input_type === "McpInput" &&
        !node.tool_mode &&
        typeof savedTool?.value === "string" &&
        savedTool.value !== "" &&
        savedTool.options?.includes(savedTool.value)
      ) {
        return;
      }

      const isRealtimeOrRefresh =
        template.real_time_refresh ||
        template.refresh_button ||
        (node.tool_mode && name === "tools_metadata");

      const hasOptions = (template.options?.length ?? 0) > 0;
      // Empty dropdowns need discovery. Fields without options, such as an MCP
      // server without a saved tool selection, can still need their first load.
      const fieldSupportsOptions = template.options !== undefined;

      const needApiKeyPrefill =
        name === "model" &&
        node.template?.api_key != null &&
        !node.template?.api_key?.value;
      // A node whose model field refreshes prefills its key through that
      // refresh. Refreshing the key as well would race it with a different
      // answer: the backend fills a default model for a key refresh but keeps
      // an empty model empty, and the two responses merge into a node that
      // matches neither, which the next open corrects again.
      const modelPrefillsApiKey =
        !!node.template?.model?.real_time_refresh ||
        !!node.template?.model?.refresh_button;

      const shouldFetchOnMount =
        isRealtimeOrRefresh &&
        ((!hasOptions && fieldSupportsOptions) ||
          (!fieldSupportsOptions && !!template.value) ||
          (name === "api_key" && !template.value && !modelPrefillsApiKey) ||
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
