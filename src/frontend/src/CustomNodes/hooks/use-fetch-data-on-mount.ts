import type { UseMutationResult } from "@tanstack/react-query";
import { useEffect } from "react";
import type { APIClassType, ResponseErrorDetailAPI } from "@/types/api";
import useAlertStore from "../../stores/alertStore";
import { mutateTemplate } from "../helpers/mutate-template";

const useFetchDataOnMount = (
  node: APIClassType,
  nodeId: string,
  setNodeClass: (node: APIClassType) => void,
  name: string,
  postTemplateValue: UseMutationResult<
    APIClassType | undefined,
    ResponseErrorDetailAPI,
    // biome-ignore lint/suspicious/noExplicitAny: legacy mutation payload
    any
  >,
) => {
  const setErrorData = useAlertStore((state) => state.setErrorData);

  useEffect(() => {
    async function fetchData() {
      const template = node.template[name];
      if (!template) return;

      const isRealtimeOrRefresh =
        template.real_time_refresh ||
        template.refresh_button ||
        (node.tool_mode && name === "tools_metadata");

      const hasOptions = (template.options?.length ?? 0) > 0;
      // Only consider empty options as a trigger if the field actually supports
      // options (e.g., dropdowns). Fields like McpInput have no options property
      // and should not trigger a fetch on mount — their real_time_refresh is
      // meant for user-initiated value changes, not initial load.
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
