import type { UseMutationResult } from "@tanstack/react-query";
import { applyPatch, compare } from "fast-json-patch";
import type {
  APIClassType,
  ResponseErrorDetailAPI,
  useMutationFunctionType,
} from "@/types/api";
import type { JsonPatchOperation } from "@/types/api/json-patch";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostTemplateValue {
  value: any;
  tool_mode?: boolean;
}

interface IPostTemplateValueParams {
  node: APIClassType;
  nodeId: string;
  parameterId: string;
}

export const usePostTemplateValue: useMutationFunctionType<
  IPostTemplateValueParams,
  IPostTemplateValue,
  APIClassType,
  ResponseErrorDetailAPI
> = ({ parameterId, nodeId, node }, options?) => {
  const { mutate } = UseRequestProcessor();

  const postTemplateValueFn = async (
    payload: IPostTemplateValue,
  ): Promise<APIClassType | undefined> => {
    const template = node.template;

    if (!template) return;
    const lastUpdated = new Date().toISOString();

    // Build JSON Patch operations
    // LIMITATION: Backend still requires full template for component rebuild
    // Future optimization: Make backend accept partial template updates
    // For now, payload is similar size to traditional PATCH, but uses consistent JSON Patch format
    const operations: JsonPatchOperation[] = [
      {
        op: "replace",
        path: "/code",
        value: template.code?.value,
      },
      {
        op: "replace",
        path: "/template",
        value: template,
      },
      {
        op: "replace",
        path: `/field/${parameterId}`,
        value: payload.value,
      },
      ...(payload.tool_mode !== undefined
        ? [
            {
              op: "replace" as const,
              path: "/tool_mode",
              value: payload.tool_mode,
            },
          ]
        : []),
    ];

    const response = await api.post(
      getURL("CUSTOM_COMPONENT", { update: "json-patch" }),
      { operations },
    );
    // If successful, apply changes efficiently using JSON Patch
    if (response.data.success) {
      // Compare old node with backend response to get minimal operations
      const backendNode = response.data.component_node;
      const operations = compare(node, backendNode);

      // Apply only the changes to the existing node (more efficient!)
      const updatedNode = { ...node };
      applyPatch(updatedNode, operations);
      updatedNode.last_updated = lastUpdated;

      return updatedNode as APIClassType;
    }

    return undefined;
  };

  const mutation: UseMutationResult<
    APIClassType,
    ResponseErrorDetailAPI,
    IPostTemplateValue
  > = mutate(
    ["usePostTemplateValue", { parameterId, nodeId }],
    postTemplateValueFn,
    {
      ...options,
      retry: 0,
    },
  );

  return mutation;
};
