import { useState } from "react";
import { useParams } from "react-router-dom";
import { Light as SyntaxHighlighter } from "react-syntax-highlighter";

import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import ToolsComponent from "@/components/core/parameterRenderComponent/components/ToolsComponent";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs-button";
import { ENABLE_MCP_COMPOSER } from "@/customization/feature-flags";
import { useCustomIsLocalConnection } from "@/customization/hooks/use-custom-is-local-connection";
import useTheme from "@/customization/hooks/use-custom-theme";
import AuthModal from "@/modals/authModal";

import useAuthStore from "@/stores/authStore";
import { useFolderStore } from "@/stores/foldersStore";
import { AUTH_METHODS } from "@/utils/mcpUtils";
import { toSpaceCase } from "@/utils/stringManipulation";
import { cn, getOS } from "@/utils/utils";
import { useMcpServer } from "../hooks/useMcpServer";

import {
  autoInstallers,
  createSyntaxHighlighterStyle,
  operatingSystemTabs,
} from "../utils/mcpServerUtils";
import { MemoizedCodeTag } from "./McpCodeDisplay";

const McpServerTab = ({ folderName }: { folderName: string }) => {
  const isDarkMode = useTheme().dark;
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const projectId = folderId ?? myCollectionId ?? "";
  const [selectedPlatform, setSelectedPlatform] = useState(
    operatingSystemTabs.find((tab) => tab.name.includes(getOS() || "windows"))
      ?.name,
  );
  const isLocalConnection = useCustomIsLocalConnection();
  const [selectedMode, setSelectedMode] = useState<string>(
    isLocalConnection ? "Auto install" : "JSON",
  );
  const {
    flowsMCPData,
    currentAuthSettings,
    isOAuthProject,
    composerUrlData,
    installedClients,
    installedMCPData,
    apiKey,
    isGeneratingApiKey,
    generateApiKey,
    isCopied,
    copyToClipboard,
    loadingMCP,
    installClient,
    authModalOpen,
    setAuthModalOpen,
    isLoading,
    handleOnNewValue,
    handleAuthSave,
    mcpJson,
  } = useMcpServer({ projectId, folderName, selectedPlatform });

  const isAutoLogin = useAuthStore((s) => s.autoLogin);
  const isAuthApiKey = ENABLE_MCP_COMPOSER
    ? currentAuthSettings?.auth_type === "apikey"
    : !isAutoLogin;
  const hasAuthentication =
    currentAuthSettings?.auth_type && currentAuthSettings.auth_type !== "none";
  const hasOAuthError = isOAuthProject && !!composerUrlData?.error_message;

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
              href="https://docs.langflow.org/mcp-server"
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
          <div className="flex flex-row justify-between pt-1">
            <ShadTooltip
              content="Flows in this project can be exposed as callable MCP tools."
              side="right"
            >
              <div className="flex items-center text-sm font-medium hover:cursor-help">
                Flows/Tools
                <ForwardedIconComponent
                  name="info"
                  className="ml-1.5 h-4 w-4 text-muted-foreground"
                  aria-hidden="true"
                />
              </div>
            </ShadTooltip>
          </div>

          <div className="flex flex-row flex-wrap gap-2 pt-2">
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
              <span className="flex gap-2 items-center text-sm cursor-default">
                <span className=" font-medium">Auth:</span>
                {!hasAuthentication ? (
                  <span className="text-accent-amber-foreground flex gap-2 text-mmd items-center">
                    <ForwardedIconComponent
                      name="AlertTriangle"
                      className="h-4 w-4 shrink-0"
                    />
                    None (public)
                  </span>
                ) : (
                  <ShadTooltip
                    content={
                      !composerUrlData?.error_message
                        ? undefined
                        : `MCP Server is not running: ${composerUrlData?.error_message}`
                    }
                  >
                    <span
                      className={cn(
                        "flex gap-2 text-mmd items-center",
                        isLoading
                          ? "text-muted-foreground"
                          : !composerUrlData?.error_message
                            ? "text-accent-emerald-foreground"
                            : "text-accent-amber-foreground",
                      )}
                    >
                      <ForwardedIconComponent
                        name={
                          isLoading
                            ? "Loader2"
                            : !composerUrlData?.error_message
                              ? "Check"
                              : "AlertTriangle"
                        }
                        className={cn(
                          "h-4 w-4 shrink-0",
                          isLoading && "animate-spin",
                        )}
                      />
                      {isLoading
                        ? "Loading..."
                        : AUTH_METHODS[
                            currentAuthSettings?.auth_type as keyof typeof AUTH_METHODS
                          ]?.label || currentAuthSettings?.auth_type}
                    </span>
                  </ShadTooltip>
                )}
              </span>

              <Button
                variant="outline"
                size="sm"
                className="!text-mmd !font-normal"
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

          <div className="flex flex-col gap-4">
            {hasOAuthError ? (
              <div className="p-4 bg-accent-red-subtle border border-accent-red-border rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <ForwardedIconComponent
                    name="AlertTriangle"
                    className="h-4 w-4 text-accent-red-foreground"
                  />
                  <span className="font-medium text-accent-red-foreground">
                    MCP Server Configuration Error
                  </span>
                </div>
                <p className="text-mmd text-accent-red-foreground">
                  {composerUrlData?.error_message}
                </p>
                <p className="text-sm text-muted-foreground mt-2">
                  Please fix the OAuth configuration in your project settings to
                  generate the MCP server configuration.
                </p>
              </div>
            ) : selectedMode === "JSON" ? (
              <>
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
                    style={createSyntaxHighlighterStyle(isDarkMode)}
                    CodeTag={({ children }) => (
                      <MemoizedCodeTag
                        isCopied={isCopied}
                        copyToClipboard={() => copyToClipboard(mcpJson)}
                        isAuthApiKey={isAuthApiKey}
                        apiKey={apiKey}
                        isGeneratingApiKey={isGeneratingApiKey}
                        generateApiKey={generateApiKey}
                      >
                        {children}
                      </MemoizedCodeTag>
                    )}
                    language="json"
                  >
                    {mcpJson}
                  </SyntaxHighlighter>
                </div>
                <div className="px-2 text-mmd text-muted-foreground">
                  Add this config to your client of choice. Need help? See the{" "}
                  <a
                    href="https://docs.langflow.org/mcp-server#connect-clients-to-use-the-servers-actions"
                    target="_blank"
                    rel="noreferrer"
                    className="text-accent-pink-foreground"
                  >
                    setup guide
                  </a>
                  .
                </div>
              </>
            ) : (
              <div className="flex flex-col gap-1 mt-4">
                {!isLocalConnection && (
                  <div className="mb-2 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-950 dark:text-amber-200">
                    <div className="flex items-center gap-3">
                      <ForwardedIconComponent
                        name="AlertTriangle"
                        className="h-4 w-4 shrink-0"
                      />
                      <span>
                        One-click install is disabled because the Langflow
                        server is not running on your local machine. Use the
                        JSON tab to configure your client manually.
                      </span>
                    </div>
                  </div>
                )}

                {autoInstallers.map((installer) => (
                  <ShadTooltip
                    key={installer.name}
                    content={
                      !installedMCPData?.find(
                        (client) => client.name === installer.name,
                      )?.available
                        ? `Install ${toSpaceCase(installer.name)} to enable auto-install.`
                        : ""
                    }
                    side="left"
                  >
                    <div className="w-full flex">
                      <Button
                        variant="ghost"
                        className="group flex flex-1 items-center justify-between disabled:text-foreground disabled:opacity-50"
                        disabled={
                          loadingMCP.includes(installer.name) ||
                          !isLocalConnection ||
                          !installedMCPData?.find(
                            (client) => client.name === installer.name,
                          )?.available
                        }
                        onClick={() =>
                          installClient(installer.name, installer.title)
                        }
                      >
                        <div className="flex items-center gap-4 text-sm font-medium">
                          <ForwardedIconComponent
                            name={installer.icon}
                            className={cn("h-5 w-5")}
                            aria-hidden="true"
                          />
                          {installer.title}
                        </div>
                        <div className="relative h-4 w-4">
                          <ForwardedIconComponent
                            name={
                              installedClients?.includes(installer.name)
                                ? "Check"
                                : loadingMCP.includes(installer.name)
                                  ? "Loader2"
                                  : "Plus"
                            }
                            className={cn(
                              "h-4 w-4 absolute top-0 left-0 opacity-100",
                              loadingMCP.includes(installer.name) &&
                                "animate-spin",
                              installedClients?.includes(installer.name) &&
                                "group-hover:opacity-0",
                            )}
                          />
                          {installedClients?.includes(installer.name) && (
                            <ForwardedIconComponent
                              name={"RefreshCw"}
                              className={cn(
                                "h-4 w-4 absolute top-0 left-0 opacity-0 group-hover:opacity-100",
                              )}
                            />
                          )}
                        </div>
                      </Button>
                    </div>
                  </ShadTooltip>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <AuthModal
        open={authModalOpen}
        setOpen={setAuthModalOpen}
        authSettings={currentAuthSettings}
        autoInstall={false}
        onSave={handleAuthSave}
      />
    </div>
  );
};

export default McpServerTab;
