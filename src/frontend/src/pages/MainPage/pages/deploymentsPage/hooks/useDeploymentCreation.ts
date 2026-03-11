import {
  type DeploymentCreatePayload,
  type DeploymentCreateResponse,
  type DeploymentListItem,
  useGetDeploymentById,
  usePostCreateDeployment,
} from "@/controllers/API/queries/deployments/use-deployments";
import useAlertStore from "@/stores/alertStore";
import { useCallback, useState } from "react";
import type { EnvVar } from "../constants";
import type {
  CreatedDeploymentUiMeta,
  DeploymentCreationState,
} from "../types";
import { validateEnvVars } from "../utils";

export type CreateDeploymentParams = {
  providerId: string;
  deploymentName: string;
  deploymentDescription: string;
  deploymentType: string;
  selectedItems: Set<string>;
  envVars: EnvVar[];
  onSubmit: () => void;
};

export const useDeploymentCreation = () => {
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const [creationState, setCreationState] =
    useState<DeploymentCreationState>("idle");
  const [createdDeploymentName, setCreatedDeploymentName] = useState("");
  const [createdDeploymentType, setCreatedDeploymentType] = useState<
    "agent" | "mcp" | null
  >(null);
  const [createdDeploymentId, setCreatedDeploymentId] = useState("");
  const [createdDeploymentItem, setCreatedDeploymentItem] =
    useState<DeploymentListItem | null>(null);
  const [createdDeploymentUiMeta, setCreatedDeploymentUiMeta] =
    useState<CreatedDeploymentUiMeta | null>(null);

  const createDeploymentMutation = usePostCreateDeployment();
  const getDeploymentByIdMutation = useGetDeploymentById();

  const resetCreatedState = useCallback(() => {
    setCreatedDeploymentItem(null);
    setCreatedDeploymentUiMeta(null);
  }, []);

  const handleCreateDeployment = ({
    providerId,
    deploymentName,
    deploymentDescription,
    deploymentType,
    selectedItems,
    envVars,
    onSubmit,
  }: CreateDeploymentParams) => {
    if (!providerId) {
      setErrorData({
        title: "No provider selected",
        list: ["Select or create a deployment provider first."],
      });
      return;
    }

    const envVarValidationErrors = validateEnvVars(envVars);
    if (envVarValidationErrors.length > 0) {
      setErrorData({
        title: "Invalid environment variables",
        list: envVarValidationErrors,
      });
      return;
    }

    const selectedCheckpointIds = Array.from(selectedItems);
    const selectedFlowCount = selectedCheckpointIds.length;
    const requestedAt = new Date().toISOString();

    const trimmedDeploymentName = deploymentName.trim();
    const trimmedDescription = deploymentDescription.trim();

    const payload: DeploymentCreatePayload = {
      provider_id: providerId,
      spec: {
        name: trimmedDeploymentName,
        description: trimmedDescription,
        type: deploymentType === "MCP" ? "mcp" : "agent",
      },
    };

    if (selectedCheckpointIds.length > 0) {
      payload.flow_versions = {
        ids: selectedCheckpointIds,
      };
    }

    const environmentVariables: Record<
      string,
      { source: "raw" | "variable"; value: string }
    > = {};
    for (const item of envVars) {
      const key = item.key.trim();
      const value = item.value.trim();
      if (key && value) {
        environmentVariables[key] = {
          source: item.globalVar ? "variable" : "raw",
          value,
        };
      }
    }

    if (Object.keys(environmentVariables).length > 0) {
      payload.config = {
        raw_payload: {
          name: trimmedDeploymentName,
          description: trimmedDescription,
          environment_variables: environmentVariables,
        },
      };
    }

    setCreationState("creating");
    setCreatedDeploymentId("");
    setCreatedDeploymentName(trimmedDeploymentName);
    setCreatedDeploymentType(payload.spec.type);
    setCreatedDeploymentUiMeta(null);
    onSubmit();

    createDeploymentMutation.mutate(payload, {
      onSuccess: async (response: DeploymentCreateResponse) => {
        setCreatedDeploymentId(response.id);
        const resultSnapshotIds = Array.isArray(response.snapshot_ids)
          ? response.snapshot_ids.filter(
              (id): id is string =>
                typeof id === "string" && id.trim().length > 0,
            )
          : [];
        setCreatedDeploymentUiMeta({
          deploymentId: response.id,
          attachedCount: resultSnapshotIds.length || selectedFlowCount,
          createdAt: requestedAt,
        });
        const deployment = await getDeploymentByIdMutation.mutateAsync({
          deploymentId: response.id,
        });
        setCreatedDeploymentItem(deployment);
        setCreationState("success");
      },
      onError: () => {
        setCreationState("error");
        setErrorData({
          title: "Could not create deployment",
          list: ["Please review provider credentials and deployment payload."],
        });
      },
    });
  };

  return {
    creationState,
    setCreationState,
    createdDeploymentName,
    createdDeploymentType,
    createdDeploymentId,
    createdDeploymentItem,
    createdDeploymentUiMeta,
    resetCreatedState,
    handleCreateDeployment,
  };
};
