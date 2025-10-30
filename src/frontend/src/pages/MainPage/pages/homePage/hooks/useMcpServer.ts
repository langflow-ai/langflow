import { useCallback, useMemo, useState } from "react";
import {
  useGetFlowsMCP,
  usePatchFlowsMCP,
} from "@/controllers/API/queries/mcp";
import { useGetProjectComposerUrl } from "@/controllers/API/queries/mcp/use-get-composer-url";
import { useGetInstalledMCP } from "@/controllers/API/queries/mcp/use-get-installed-mcp";
import { usePatchInstallMCP } from "@/controllers/API/queries/mcp/use-patch-install-mcp";
import { ENABLE_MCP_COMPOSER } from "@/customization/feature-flags";
import { customGetMCPUrl } from "@/customization/utils/custom-mcp-url";
import useAlertStore from "@/stores/alertStore";
import useAuthStore from "@/stores/authStore";
import type { InputFieldType } from "@/types/api";
import { FlowType } from "@/types/flow";
import type { AuthSettingsType, MCPSettingsType } from "@/types/mcp";
import {
  buildMcpServerJson,
  extractInstalledClientNames,
  getAuthHeaders,
  MAX_MCP_SERVER_NAME_LENGTH,
  mapFlowsToTools,
  type ToolFlow,
} from "../utils/mcpServerUtils";

type InstalledMCPItem = { name?: string; available?: boolean };

type State = {
  apiKey: string;
  isGeneratingApiKey: boolean;
  isCopied: boolean;
  loadingMCP: string[];
  authModalOpen: boolean;
};

export const useMcpServer = ({
  projectId,
  folderName,
  selectedPlatform,
}: {
  projectId: string;
  folderName?: string;
  selectedPlatform?: string;
}) => {
  const setSuccessData = useAlertStore((s) => s.setSuccessData);
  const setErrorData = useAlertStore((s) => s.setErrorData);

  const { data: mcpProjectData, isLoading: isLoadingMCPProjectData } =
    useGetFlowsMCP({ projectId });
  const { mutate: patchFlowsMCP, isPending: isPatchingFlowsMCP } =
    usePatchFlowsMCP({ project_id: projectId });
  const { data: composerUrlData } = useGetProjectComposerUrl(
    { projectId },
    {
      enabled:
        !!projectId &&
        mcpProjectData?.auth_settings?.auth_type === "oauth" &&
        ENABLE_MCP_COMPOSER &&
        !isPatchingFlowsMCP,
    },
  );
  const { data: installedMCPData } = useGetInstalledMCP({ projectId });
  const { mutate: patchInstallMCP } = usePatchInstallMCP({
    project_id: projectId,
  });

  const flows = mcpProjectData?.tools ?? [];
  const currentAuthSettings = mcpProjectData?.auth_settings;
  const authType = currentAuthSettings?.auth_type ?? null;
  const isOAuthProject = authType === "oauth" && ENABLE_MCP_COMPOSER;

  const [s, setS] = useState<State>({
    apiKey: "",
    isGeneratingApiKey: false,
    isCopied: false,
    loadingMCP: [],
    authModalOpen: false,
  });
  // auth store selectors
  const apiKeyFromStore = useAuthStore((st) => st.apiKey);
  const isAutoLoginFromStore = useAuthStore((st) => st.autoLogin);

  const flowsMCPData = useMemo(() => mapFlowsToTools(flows), [flows]);
  const installedClients = useMemo(
    () => extractInstalledClientNames(installedMCPData),
    [installedMCPData],
  );

  const apiUrl = useMemo(
    () =>
      customGetMCPUrl(
        projectId,
        isOAuthProject &&
          !!composerUrlData?.sse_url &&
          composerUrlData?.uses_composer,
        composerUrlData?.sse_url,
      ),
    [projectId, isOAuthProject, composerUrlData],
  );

  const generateApiKey = useCallback(async () => {
    try {
      setS((prev) => ({ ...prev, isGeneratingApiKey: true }));
      const { createApiKey } = await import("@/controllers/API");
      const res = await createApiKey(`MCP Server ${folderName ?? ""}`);
      if (res?.api_key) {
        setS((prev) => ({ ...prev, apiKey: res.api_key }));
      }
    } catch (e) {
      console.error("Error generating API key:", e);
      setErrorData({
        title: "Error generating API key",
        list: [(e as Error).message],
      });
    } finally {
      setS((prev) => ({ ...prev, isGeneratingApiKey: false }));
    }
  }, [folderName, setErrorData]);

  const copyToClipboard = useCallback((payload: string) => {
    navigator.clipboard?.writeText(payload).then(
      () => {
        setS((p) => ({ ...p, isCopied: true }));
        setTimeout(() => setS((p) => ({ ...p, isCopied: false })), 1000);
      },
      () => {},
    );
  }, []);

  const installClient = useCallback(
    (clientName: string, clientTitle?: string) => {
      setS((p) => ({ ...p, loadingMCP: [...p.loadingMCP, clientName] }));
      patchInstallMCP(
        { client: clientName },
        {
          onSuccess: () => {
            setSuccessData({
              title: `MCP Server installed successfully on ${clientTitle ?? clientName}. You may need to restart your client to see the changes.`,
            });
            setS((p) => ({
              ...p,
              loadingMCP: p.loadingMCP.filter((n) => n !== clientName),
            }));
          },
          onError: (e) => {
            const message = (e as { message?: string })?.message ?? String(e);
            setErrorData({
              title: `Failed to install MCP Server on ${clientTitle ?? clientName}`,
              list: [message],
            });
            setS((p) => ({
              ...p,
              loadingMCP: p.loadingMCP.filter((n) => n !== clientName),
            }));
          },
        },
      );
    },
    [patchInstallMCP, setSuccessData, setErrorData],
  );

  const handleOnNewValue = useCallback(
    (changes: Partial<InputFieldType>) => {
      if (!changes.value || !Array.isArray(changes.value)) return;

      const settings: MCPSettingsType[] = (changes.value as ToolFlow[]).map(
        (flow: ToolFlow) => ({
          id: flow.id,
          action_name: flow.name,
          action_description: flow.description,
          mcp_enabled: !!flow.status,
        }),
      );
      patchFlowsMCP({
        settings,
        auth_settings: ENABLE_MCP_COMPOSER
          ? currentAuthSettings
          : { auth_type: "none" },
      });
    },
    [patchFlowsMCP, currentAuthSettings],
  );

  const handleAuthSave = useCallback(
    (authSettings: AuthSettingsType) => {
      const settings: MCPSettingsType[] = (flows ?? []).map((f) => ({
        id: f.id,
        action_name: f.action_name,
        action_description: f.action_description,
        mcp_enabled: f.mcp_enabled,
      }));
      patchFlowsMCP({ settings, auth_settings: authSettings });
    },
    [patchFlowsMCP, flows],
  );

  const authHeadersFragment = useMemo(
    () =>
      getAuthHeaders({
        enableComposer: ENABLE_MCP_COMPOSER,
        authType,
        isAutoLogin: !!isAutoLoginFromStore,
        apiKey: apiKeyFromStore ?? s.apiKey,
      }),
    [authType, isAutoLoginFromStore, apiKeyFromStore],
  );

  const composerError = composerUrlData?.error_message ?? null;

  const mcpJson = useMemo(() => {
    return buildMcpServerJson({
      folderName,
      selectedPlatform,
      apiUrl,
      isOAuthProject,
      authHeadersFragment,
      maxNameLength: MAX_MCP_SERVER_NAME_LENGTH,
    });
  }, [
    folderName,
    selectedPlatform,
    apiUrl,
    isOAuthProject,
    authHeadersFragment,
  ]);

  const availableMap = useMemo(() => {
    const map: Record<string, boolean> = {};
    (installedMCPData ?? []).forEach(
      (c: InstalledMCPItem | Record<string, unknown>) => {
        const name =
          (c as InstalledMCPItem)?.name ?? (c as Record<string, unknown>)?.name;
        const available = (c as Record<string, unknown>)?.available;
        if (name) map[String(name)] = !!available;
      },
    );
    return map;
  }, [installedMCPData]);

  const isInstalling = (clientName: string) =>
    s.loadingMCP.includes(clientName);

  const hasAuthentication = !!(
    currentAuthSettings?.auth_type && currentAuthSettings.auth_type !== "none"
  );
  const isAuthApiKey = ENABLE_MCP_COMPOSER
    ? authType === "apikey"
    : !isAutoLoginFromStore;
  const hasOAuthError = isOAuthProject && !!composerUrlData?.error_message;

  return {
    flows,
    flowsMCPData,
    currentAuthSettings,
    // auth / composer
    isOAuthProject,
    authType,
    hasAuthentication,
    isAuthApiKey,
    composerUrlData,
    composerError,
    hasOAuthError,
    // mcp json + url
    apiUrl,
    authHeadersFragment,
    mcpJson,
    // installed clients
    installedClients,
    installedMCPData,
    availableMap,
    isInstalling,
    // api key & ui
    apiKey: apiKeyFromStore ?? s.apiKey,
    isGeneratingApiKey: s.isGeneratingApiKey,
    generateApiKey,
    isCopied: s.isCopied,
    copyToClipboard,
    loadingMCP: s.loadingMCP,
    installClient,
    authModalOpen: s.authModalOpen,
    setAuthModalOpen: (v: boolean) => setS((p) => ({ ...p, authModalOpen: v })),
    isLoading: isLoadingMCPProjectData || isPatchingFlowsMCP,
    handleOnNewValue,
    handleAuthSave,
  };
};
