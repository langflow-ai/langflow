import { memo, type ReactNode, useCallback, useState } from "react";
import { useParams } from "react-router-dom";
import { Light as SyntaxHighlighter } from "react-syntax-highlighter";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import ToolsComponent from "@/components/core/parameterRenderComponent/components/ToolsComponent";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs-button";
import { MAX_MCP_SERVER_NAME_LENGTH } from "@/constants/constants";
import { createApiKey } from "@/controllers/API";
import {
  useGetFlowsMCP,
  usePatchFlowsMCP,
} from "@/controllers/API/queries/mcp";
import { useGetInstalledMCP } from "@/controllers/API/queries/mcp/use-get-installed-mcp";
import { usePatchInstallMCP } from "@/controllers/API/queries/mcp/use-patch-install-mcp";
import { ENABLE_MCP_COMPOSER } from "@/customization/feature-flags";
import { useCustomIsLocalConnection } from "@/customization/hooks/use-custom-is-local-connection";
import useTheme from "@/customization/hooks/use-custom-theme";
import { customGetMCPUrl } from "@/customization/utils/custom-mcp-url";
import AuthModal from "@/modals/authModal";
import useAlertStore from "@/stores/alertStore";
import useAuthStore from "@/stores/authStore";
import { useFolderStore } from "@/stores/foldersStore";
import type { AuthSettingsType, MCPSettingsType } from "@/types/mcp";
import { AUTH_METHODS } from "@/utils/mcpUtils";
import { parseString } from "@/utils/stringManipulation";
import { cn, getOS } from "@/utils/utils";

// Define interface for MemoizedCodeTag props
interface MemoizedCodeTagProps {
  children: ReactNode;
  isCopied: boolean;
  copyToClipboard: () => void;
  isAutoLogin: boolean | null;
  apiKey: string;
  isGeneratingApiKey: boolean;
  generateApiKey: () => void;
}

// Memoized CodeTag to prevent re-renders when parent components re-render
const MemoizedCodeTag = memo(
  ({
    children,
    isCopied,
    copyToClipboard,
    isAutoLogin,
    apiKey,
    isGeneratingApiKey,
    generateApiKey,
  }: MemoizedCodeTagProps) => (
    <div className="relative bg-background text-[13px]">
      <div className="absolute right-4 top-4 flex items-center gap-6">
        {!isAutoLogin && (
          <Button
            unstyled
            className="flex items-center gap-2 font-sans text-muted-foreground hover:text-foreground"
            disabled={apiKey !== ""}
            loading={isGeneratingApiKey}
            onClick={generateApiKey}
          >
            <ForwardedIconComponent
              name={"key"}
              className="h-4 w-4"
              aria-hidden="true"
            />
            <span>
              {apiKey === "" ? "Generate API key" : "API key generated"}
            </span>
          </Button>
        )}
        <Button
          unstyled
          size="icon"
          className={cn("h-4 w-4 text-muted-foreground hover:text-foreground")}
          onClick={copyToClipboard}
        >
          <ForwardedIconComponent
            name={isCopied ? "check" : "copy"}
            className="h-4 w-4"
            aria-hidden="true"
          />
        </Button>
      </div>
      <div className="overflow-x-auto p-4">
        <span>{children}</span>
      </div>
    </div>
  ),
);
MemoizedCodeTag.displayName = "MemoizedCodeTag";

const autoInstallers = [
  {
    name: "cursor",
    title: "Cursor",
    icon: "Cursor",
  },
  {
    name: "claude",
    title: "Claude",
    icon: "Claude",
  },
  {
    name: "windsurf",
    title: "Windsurf",
    icon: "Windsurf",
  },
];

const operatingSystemTabs = [
  {
    name: "macoslinux",
    title: "macOS/Linux",
    icon: "FaApple",
  },
  {
    name: "windows",
    title: "Windows",
    icon: "FaWindows",
  },
  {
    name: "wsl",
    title: "WSL",
    icon: "FaLinux",
  },
];

const McpServerTab = ({ folderName }: { folderName: string }) => {
  const isDarkMode = useTheme().dark;
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const projectId = folderId ?? myCollectionId ?? "";
  const [isCopied, setIsCopied] = useState(false);
  const [apiKey, setApiKey] = useState<string>("");
  const [isGeneratingApiKey, setIsGeneratingApiKey] = useState(false);
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const { data: mcpProjectData } = useGetFlowsMCP({ projectId });
  const { mutate: patchFlowsMCP } = usePatchFlowsMCP({ project_id: projectId });

  // Extract tools and auth_settings from the response
  const flowsMCP = mcpProjectData?.tools || [];
  const currentAuthSettings = mcpProjectData?.auth_settings;
  const { mutate: patchInstallMCP } = usePatchInstallMCP({
    project_id: projectId,
  });

  const { data: installedMCP } = useGetInstalledMCP({ projectId });

  const [selectedPlatform, setSelectedPlatform] = useState(
    operatingSystemTabs.find((tab) => tab.name.includes(getOS() || "windows"))
      ?.name,
  );

  const isAutoLogin = useAuthStore((state) => state.autoLogin);

  // Check if the current connection is local
  const isLocalConnection = useCustomIsLocalConnection();

  const [selectedMode, setSelectedMode] = useState(
    isLocalConnection ? "Auto install" : "JSON",
  );

  const handleOnNewValue = (value: any) => {
    const flowsMCPData: MCPSettingsType[] = value.value.map((flow: any) => ({
      id: flow.id,
      action_name: flow.name,
      action_description: flow.description,
      mcp_enabled: flow.status,
    }));

    // Prepare the request with both settings and auth_settings
    // If ENABLE_MCP_COMPOSER is false, always use "none" for auth_type
    const finalAuthSettings = ENABLE_MCP_COMPOSER
      ? currentAuthSettings
      : { auth_type: "none" };

    const requestData = {
      settings: flowsMCPData,
      auth_settings: finalAuthSettings,
    };

    patchFlowsMCP(requestData);
  };

  const handleAuthSave = (authSettings: AuthSettingsType) => {
    // Update the current flows with the new auth settings
    const flowsMCPData: MCPSettingsType[] =
      flowsMCP?.map((flow) => ({
        id: flow.id,
        action_name: flow.action_name,
        action_description: flow.action_description,
        mcp_enabled: flow.mcp_enabled,
      })) || [];

    const requestData = {
      settings: flowsMCPData,
      auth_settings: authSettings,
    };

    patchFlowsMCP(requestData);
  };

  const flowsMCPData = flowsMCP?.map((flow) => ({
    id: flow.id,
    name: flow.action_name,
    description: flow.action_description,
    display_name: flow.name,
    display_description: flow.description,
    status: flow.mcp_enabled,
    tags: [flow.name],
  }));

  const syntaxHighlighterStyle = {
    "hljs-string": {
      color: isDarkMode ? "hsla(158, 64%, 52%, 1)" : "#059669", // Accent Green
    },
    "hljs-attr": {
      color: isDarkMode ? "hsla(329, 86%, 70%, 1)" : "#DB2777", // Accent Pink
    },
  };

  const apiUrl = customGetMCPUrl(projectId);

  // Generate auth headers based on the authentication type
  const getAuthHeaders = () => {
    // If MCP auth is disabled, use the previous API key behavior
    if (!ENABLE_MCP_COMPOSER) {
      if (isAutoLogin) return "";
      return `
        "--headers",
        "x-api-key",
        "${apiKey || "YOUR_API_KEY"}",`;
    }

    if (!currentAuthSettings || currentAuthSettings.auth_type === "none") {
      return "";
    }

    switch (currentAuthSettings.auth_type) {
      case "apikey":
        return `
        "--headers",
        "x-api-key",
        "${currentAuthSettings.api_key || "YOUR_API_KEY"}",`;
      case "basic":
        return `
        "--headers",
        "Authorization",
        "Basic ${btoa(
          `${currentAuthSettings.username || "USERNAME"}:${
            currentAuthSettings.password || "PASSWORD"
          }`,
        )}",`;
      case "bearer":
        return `
        "--headers",
        "Authorization",
        "Bearer ${currentAuthSettings.bearer_token || "YOUR_BEARER_TOKEN"}",`;
      case "iam":
        return `
        "--headers",
        "x-api-key",
        "${currentAuthSettings.api_key || "YOUR_IAM_TOKEN"}",
        "--headers",
        "x-iam-endpoint",
        "${currentAuthSettings.iam_endpoint || "YOUR_IAM_ENDPOINT"}",`;
      case "oauth":
        return `
        "--auth-type",
        "oauth"`;
      default:
        return "";
    }
  };

  const getEnvVars = () => {
    if (!ENABLE_MCP_COMPOSER || currentAuthSettings?.auth_type === "none")
      return "";
    if (currentAuthSettings?.auth_type === "oauth") {
      return `
      "env": {
        "OAUTH_HOST": "${currentAuthSettings.oauth_host || "YOUR_OAUTH_HOST"}",
        "OAUTH_PORT": "${currentAuthSettings.oauth_port || "YOUR_OAUTH_PORT"}",
        "OAUTH_SERVER_URL": "${currentAuthSettings.oauth_server_url || "YOUR_OAUTH_SERVER_URL"}",
        "OAUTH_CALLBACK_PATH": "${currentAuthSettings.oauth_callback_path || "YOUR_OAUTH_CALLBACK_PATH"}",
        "OAUTH_CLIENT_ID": "${currentAuthSettings.oauth_client_id || "YOUR_OAUTH_CLIENT_ID"}",
        "OAUTH_CLIENT_SECRET": "${currentAuthSettings.oauth_client_secret || "YOUR_OAUTH_CLIENT_SECRET"}",
        "OAUTH_AUTH_URL": "${currentAuthSettings.oauth_auth_url || "YOUR_OAUTH_AUTH_URL"}",
        "OAUTH_TOKEN_URL": "${currentAuthSettings.oauth_token_url || "YOUR_OAUTH_TOKEN_URL"}",
        "OAUTH_MCP_SCOPE": "${currentAuthSettings.oauth_mcp_scope || "YOUR_OAUTH_MCP_SCOPE"}",
        "OAUTH_PROVIDER_SCOPE": "${currentAuthSettings.oauth_provider_scope || "YOUR_OAUTH_PROVIDER_SCOPE"}",
      }`;
    }
    return "";
  };

  const MCP_SERVER_JSON = `{
  "mcpServers": {
    "lf-${parseString(folderName ?? "project", [
      "snake_case",
      "no_blank",
      "lowercase",
    ]).slice(0, MAX_MCP_SERVER_NAME_LENGTH - 4)}": {
      "command": "${
        selectedPlatform === "windows"
          ? "cmd"
          : selectedPlatform === "wsl"
            ? "wsl"
            : "uvx"
      }",
      "args": [
        ${
          selectedPlatform === `windows`
            ? `"/c",
        "uvx",
        `
            : selectedPlatform === "wsl"
              ? `"uvx",
        `
              : ""
        }"${ENABLE_MCP_COMPOSER ? "mcp-composer" : "mcp-proxy"}",${getAuthHeaders()}
        "${apiUrl}"
      ]${ENABLE_MCP_COMPOSER && currentAuthSettings?.auth_type === "oauth" ? `,` : ""}${getEnvVars()}
    }
  }
}`;

  const MCP_SERVER_TUTORIAL_LINK =
    "https://docs.langflow.org/mcp-server#connect-clients-to-use-the-servers-actions";

  const MCP_SERVER_DEPLOY_TUTORIAL_LINK =
    "https://docs.langflow.org/mcp-server";

  const copyToClipboard = useCallback(() => {
    navigator.clipboard
      .writeText(MCP_SERVER_JSON)
      .then(() => {
        setIsCopied(true);
        setTimeout(() => {
          setIsCopied(false);
        }, 1000);
      })
      .catch((err) => console.error("Failed to copy text: ", err));
  }, [MCP_SERVER_JSON]);

  const generateApiKey = useCallback(() => {
    setIsGeneratingApiKey(true);
    createApiKey(`MCP Server ${folderName}`)
      .then((res) => {
        setApiKey(res["api_key"]);
      })
      .catch(() => {})
      .finally(() => {
        setIsGeneratingApiKey(false);
      });
  }, [folderName]);

  const [loadingMCP, setLoadingMCP] = useState<string[]>([]);

  // Check if authentication is configured (not "none")
  const hasAuthentication =
    currentAuthSettings?.auth_type && currentAuthSettings.auth_type !== "none";

  return (
    <div>
      <div className="flex justify-between gap-4 items-start">
        <div>
          <div className="pb-2 font-medium" data-testid="mcp-server-title">
            MCP Server
          </div>
          <div className="pb-4 text-mmd text-muted-foreground">
            Access your Project's flows as Tools within a MCP Server. Learn more
            in our
            <a
              className="text-accent-pink-foreground"
              href={MCP_SERVER_DEPLOY_TUTORIAL_LINK}
              target="_blank"
              rel="noreferrer"
            >
              {" "}
              Projects as MCP Servers guide.
            </a>
          </div>
        </div>
      </div>
      <div className="flex flex-col justify-between gap-8 xl:flex-row">
        <div className="w-full xl:w-2/5">
          <div className="flex flex-row flex-wrap gap-2">
            <ToolsComponent
              value={flowsMCPData}
              title="MCP Server Tools"
              description="Select tools to add to this server"
              handleOnNewValue={handleOnNewValue}
              id="mcp-server-tools"
              button_description="Edit Tools"
              editNode={false}
              isAction
              disabled={false}
            />
          </div>
        </div>
        <div className="flex flex-1 flex-col gap-4 overflow-hidden">
          {ENABLE_MCP_COMPOSER && (
            <div className="flex justify-between">
              <span className="flex gap-2 items-center">
                Auth:
                {!hasAuthentication ? (
                  <span className="text-accent-amber-foreground flex gap-2 text-mmd items-center">
                    <ForwardedIconComponent
                      name="AlertTriangle"
                      className="h-4 w-4 shrink-0"
                    />
                    None (public)
                  </span>
                ) : (
                  <span className="text-accent-emerald-foreground flex gap-2 text-mmd items-center">
                    <ForwardedIconComponent
                      name="Check"
                      className="h-4 w-4 shrink-0"
                    />
                    {AUTH_METHODS[
                      currentAuthSettings.auth_type as keyof typeof AUTH_METHODS
                    ]?.label || currentAuthSettings.auth_type}
                  </span>
                )}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setAuthModalOpen(true)}
              >
                <ForwardedIconComponent
                  name="Fingerprint"
                  className="h-4 w-4 shrink-0"
                />
                {hasAuthentication ? "Edit Auth" : "Add Auth"}
              </Button>
            </div>
          )}
          <div className={cn("flex flex-col", !ENABLE_MCP_COMPOSER && "mt-2")}>
            <div className="flex flex-row justify-start border-b border-border">
              {[{ name: "Auto install" }, { name: "JSON" }].map((item) => (
                <Button
                  unstyled
                  key={item.name}
                  className={`flex h-6 flex-row items-end gap-2 text-nowrap border-b-2 border-border border-b-transparent !py-1 font-medium ${
                    selectedMode === item.name
                      ? "border-b-2 border-black dark:border-b-white"
                      : "text-muted-foreground hover:text-foreground"
                  } px-3 py-2 text-[13px]`}
                  onClick={() => setSelectedMode(item.name)}
                >
                  <span>{item.name}</span>
                </Button>
              ))}
            </div>
          </div>
          {selectedMode === "JSON" && (
            <>
              <div className="flex flex-col gap-4">
                <Tabs
                  value={selectedPlatform}
                  onValueChange={setSelectedPlatform}
                >
                  <TabsList>
                    {operatingSystemTabs.map((tab) => (
                      <TabsTrigger
                        className="flex items-center gap-2"
                        key={tab.name}
                        value={tab.name}
                      >
                        <ForwardedIconComponent
                          name={tab.icon}
                          aria-hidden="true"
                        />
                        {tab.title}
                      </TabsTrigger>
                    ))}
                  </TabsList>
                </Tabs>
                <div className="overflow-hidden rounded-lg border border-border">
                  <SyntaxHighlighter
                    style={syntaxHighlighterStyle}
                    CodeTag={({ children }) => (
                      <MemoizedCodeTag
                        isCopied={isCopied}
                        copyToClipboard={copyToClipboard}
                        isAutoLogin={isAutoLogin}
                        apiKey={apiKey}
                        isGeneratingApiKey={isGeneratingApiKey}
                        generateApiKey={generateApiKey}
                      >
                        {children}
                      </MemoizedCodeTag>
                    )}
                    language="json"
                  >
                    {MCP_SERVER_JSON}
                  </SyntaxHighlighter>
                </div>
              </div>
              <div className="px-2 text-mmd text-muted-foreground">
                Add this config to your client of choice. Need help? See the{" "}
                <a
                  href={MCP_SERVER_TUTORIAL_LINK}
                  target="_blank"
                  rel="noreferrer"
                  className="text-accent-pink-foreground"
                >
                  setup guide
                </a>
                .
              </div>
            </>
          )}
          {selectedMode === "Auto install" && (
            <div className="flex flex-col gap-1">
              {!isLocalConnection && (
                <div className="mb-2 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-950 dark:text-amber-200">
                  <div className="flex items-center gap-3">
                    <ForwardedIconComponent
                      name="AlertTriangle"
                      className="h-4 w-4 shrink-0"
                    />
                    <span>
                      One-click install is disabled because the Langflow server
                      is not running on your local machine. Use the JSON tab to
                      configure your client manually.
                    </span>
                  </div>
                </div>
              )}
              {autoInstallers.map((installer) => (
                <Button
                  key={installer.name}
                  variant="ghost"
                  className="flex items-center justify-between disabled:text-foreground disabled:opacity-50"
                  disabled={
                    installedMCP?.includes(installer.name) ||
                    loadingMCP.includes(installer.name) ||
                    !isLocalConnection
                  }
                  onClick={() => {
                    setLoadingMCP([...loadingMCP, installer.name]);
                    patchInstallMCP(
                      {
                        client: installer.name,
                      },
                      {
                        onSuccess: () => {
                          setSuccessData({
                            title: `MCP Server installed successfully on ${installer.title}. You may need to restart your client to see the changes.`,
                          });
                          setLoadingMCP(
                            loadingMCP.filter(
                              (name) => name !== installer.name,
                            ),
                          );
                        },
                        onError: (e) => {
                          setErrorData({
                            title: `Failed to install MCP Server on ${installer.title}`,
                            list: [e.message],
                          });
                          setLoadingMCP(
                            loadingMCP.filter(
                              (name) => name !== installer.name,
                            ),
                          );
                        },
                      },
                    );
                  }}
                >
                  <div className="flex items-center gap-4 text-sm font-medium">
                    <ForwardedIconComponent
                      name={installer.icon}
                      className={cn("h-5 w-5")}
                      aria-hidden="true"
                    />
                    {installer.title}
                  </div>

                  <ForwardedIconComponent
                    name={
                      installedMCP?.includes(installer.name)
                        ? "Check"
                        : loadingMCP.includes(installer.name)
                          ? "Loader2"
                          : "Plus"
                    }
                    className={cn(
                      "h-4 w-4",
                      loadingMCP.includes(installer.name) && "animate-spin",
                    )}
                  />
                </Button>
              ))}
            </div>
          )}
        </div>
      </div>
      {ENABLE_MCP_COMPOSER && (
        <AuthModal
          open={authModalOpen}
          setOpen={setAuthModalOpen}
          authSettings={currentAuthSettings}
          onSave={handleAuthSave}
        />
      )}
    </div>
  );
};

export default McpServerTab;
