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

      const shouldFetchOnMount =
        isRealtimeOrRefresh &&
        ((!hasOptions && fieldSupportsOptions) ||
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
