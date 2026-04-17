import {
  type Dispatch,
  type SetStateAction,
  useEffect,
  useMemo,
  useRef,
} from "react";
import { useParams } from "react-router-dom";
import { useGetDeploymentConfigs } from "@/controllers/API/queries/deployments/use-get-deployment-configs";
import { useGetFlowVersions } from "@/controllers/API/queries/flow-version/use-get-flow-versions";
import { useGetRefreshFlowsQuery } from "@/controllers/API/queries/flows/use-get-refresh-flows-query";
import { useGetGlobalVariables } from "@/controllers/API/queries/variables";
import { useFolderStore } from "@/stores/foldersStore";
import type { ConnectionItem } from "../types";

interface UseAttachFlowsDataParams {
  initialFlowId?: string;
  selectedFlowId: string | null;
  selectedVersionByFlow: Map<string, { versionId: string; versionTag: string }>;
  selectedInstanceId?: string;
  setConnections: Dispatch<SetStateAction<ConnectionItem[]>>;
}

export function useAttachFlowsData({
  initialFlowId,
  selectedFlowId,
  selectedVersionByFlow,
  selectedInstanceId,
  setConnections,
}: UseAttachFlowsDataParams) {
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const currentFolderId = folderId ?? myCollectionId;

  const { data: flowsData } = useGetRefreshFlowsQuery(
    {
      get_all: true,
      remove_example_flows: true,
    },
    { enabled: !!currentFolderId },
  );

  const flows = useMemo(() => {
    const list = Array.isArray(flowsData) ? flowsData : [];
    const filtered = list.filter(
      (flow) =>
        !flow.is_component &&
        (flow.folder_id === currentFolderId || flow.id === initialFlowId),
    );

    if (selectedVersionByFlow.size > 0) {
      filtered.sort((a, b) => {
        const aAttached = selectedVersionByFlow.has(a.id) ? 0 : 1;
        const bAttached = selectedVersionByFlow.has(b.id) ? 0 : 1;
        return aAttached - bAttached;
      });
    }

    return filtered;
  }, [flowsData, currentFolderId, initialFlowId, selectedVersionByFlow]);

  const providerId = selectedInstanceId ?? "";
  const { data: configsData } = useGetDeploymentConfigs(
    { providerId },
    { enabled: !!providerId },
  );

  const seededExistingConnections = useRef(false);
  useEffect(() => {
    if (seededExistingConnections.current || !configsData?.configs?.length) {
      return;
    }
    seededExistingConnections.current = true;

    const existingConnections: ConnectionItem[] = configsData.configs
      .filter((config) => config.environment !== "live")
      .map((config) => ({
        id: config.app_id,
        connectionId: config.connection_id,
        name: config.app_id,
        environment: config.environment,
        variableCount: 0,
        isNew: false,
        environmentVariables: {},
      }));

    setConnections((prev) => {
      const existingIds = new Set(prev.map((connection) => connection.id));
      const toAdd = existingConnections.filter(
        (connection) => !existingIds.has(connection.id),
      );
      return [...toAdd, ...prev];
    });
  }, [configsData, setConnections]);

  const effectiveFlowId = selectedFlowId ?? flows[0]?.id ?? null;

  const { data: versionResponse, isLoading: isLoadingVersions } =
    useGetFlowVersions(
      { flowId: effectiveFlowId ?? "" },
      { enabled: !!effectiveFlowId },
    );

  const versions = versionResponse?.entries ?? [];
  const selectedFlow = useMemo(
    () => flows.find((flow) => flow.id === effectiveFlowId),
    [flows, effectiveFlowId],
  );

  const { data: globalVariables } = useGetGlobalVariables();
  const globalVariableOptions = useMemo(
    () => (globalVariables ?? []).map((variable) => variable.name),
    [globalVariables],
  );

  return {
    flows,
    effectiveFlowId,
    versions,
    isLoadingVersions,
    selectedFlow,
    globalVariableOptions,
  };
}
