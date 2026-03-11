import { getURL } from "@/controllers/API/helpers/constants";
import { usePostDetectDeploymentEnvVars } from "@/controllers/API/queries/deployments/use-deployments";
import type { FlowType } from "@/types/flow";
import type { FlowHistoryEntry } from "@/types/flow/history";
import { useEffect, useRef, useState } from "react";
import type { EnvVar } from "../constants";
import type { FlowCheckpointGroup } from "../types";
import { fetchFlowHistoryWithDedupe, formatDateLabel } from "../utils";

export type UseCheckpointsParams = {
  flows: FlowType[];
  newDeploymentOpen: boolean;
  selectedItems: Set<string>;
  currentStep: number;
  envVars: EnvVar[];
  setEnvVars: (vars: EnvVar[]) => void;
};

export const useCheckpoints = ({
  flows,
  newDeploymentOpen,
  selectedItems,
  currentStep,
  envVars,
  setEnvVars,
}: UseCheckpointsParams) => {
  const [checkpointGroups, setCheckpointGroups] = useState<
    FlowCheckpointGroup[]
  >([]);
  const [detectedEnvVars, setDetectedEnvVars] = useState<EnvVar[]>([]);
  const prevSelectedKeyRef = useRef("");

  const { mutateAsync: detectDeploymentEnvVars } =
    usePostDetectDeploymentEnvVars();

  // Load checkpoints when modal opens
  useEffect(() => {
    let cancelled = false;
    const loadCheckpoints = async () => {
      if (!newDeploymentOpen || flows.length === 0) {
        setCheckpointGroups([]);
        return;
      }
      const responses = await Promise.all(
        flows.map(async (flow) => {
          try {
            const response = await fetchFlowHistoryWithDedupe(
              `${getURL("FLOWS")}/${flow.id}/history/?limit=20&offset=0`,
            );
            return { flow, entries: response.entries ?? [] };
          } catch {
            return { flow, entries: [] as FlowHistoryEntry[] };
          }
        }),
      );
      const groups = responses.map(({ flow, entries }) => ({
        flowId: flow.id,
        flowName: flow.name,
        checkpoints: entries.map((entry) => ({
          id: entry.id,
          name: entry.version_tag
            ? `Version ${entry.version_tag}`
            : "Checkpoint",
          updatedDate: formatDateLabel(entry.created_at),
        })),
      }));
      if (!cancelled) {
        setCheckpointGroups(groups);
      }
    };
    loadCheckpoints();
    return () => {
      cancelled = true;
    };
  }, [flows, newDeploymentOpen]);

  // Reset on modal close
  useEffect(() => {
    if (!newDeploymentOpen) {
      prevSelectedKeyRef.current = "";
      setDetectedEnvVars([]);
    }
  }, [newDeploymentOpen]);

  // Detect env vars when selection changes
  useEffect(() => {
    if (!newDeploymentOpen || selectedItems.size === 0) {
      setDetectedEnvVars([]);
      return;
    }

    let cancelled = false;
    const checkpointIds = Array.from(selectedItems);
    const detect = async () => {
      try {
        const response = await detectDeploymentEnvVars({
          reference_ids: checkpointIds,
        });
        if (!cancelled) {
          setDetectedEnvVars(
            (response.variables || []).map((item) => ({
              key: item.global_variable_name ?? item.key,
              value: item.global_variable_name ?? "",
              globalVar: Boolean(item.global_variable_name),
              deploymentKey: item.key,
            })),
          );
        }
      } catch {
        if (!cancelled) {
          setDetectedEnvVars([]);
        }
      }
    };
    void detect();
    return () => {
      cancelled = true;
    };
  }, [newDeploymentOpen, selectedItems, detectDeploymentEnvVars]);

  // Sync detected env vars into form state
  useEffect(() => {
    if (!newDeploymentOpen || currentStep < 3) {
      return;
    }
    if (envVars.length > 0 || detectedEnvVars.length === 0) {
      return;
    }
    setEnvVars(detectedEnvVars);
  }, [
    currentStep,
    detectedEnvVars,
    envVars.length,
    newDeploymentOpen,
    setEnvVars,
  ]);

  return {
    checkpointGroups,
    detectedEnvVars,
  };
};
