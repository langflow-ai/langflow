import { useState } from "react";
import { useParams } from "react-router-dom";

import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { ENABLE_MCP_COMPOSER } from "@/customization/feature-flags";
import { useCustomIsLocalConnection } from "@/customization/hooks/use-custom-is-local-connection";
import useTheme from "@/customization/hooks/use-custom-theme";
import AuthModal from "@/modals/authModal";

import { useFolderStore } from "@/stores/foldersStore";
import { cn, getOS } from "@/utils/utils";
import { useMcpServer } from "../hooks/useMcpServer";

import { operatingSystemTabs } from "../utils/mcpServerUtils";
import { McpAuthSection } from "./McpAuthSection";
import { McpAutoInstallContent } from "./McpAutoInstallContent";
import { McpFlowsSection } from "./McpFlowsSection";
import { McpJsonContent } from "./McpJsonContent";

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
    hasAuthentication,
    isAuthApiKey,
    hasOAuthError,
  } = useMcpServer({ projectId, folderName, selectedPlatform });

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
        <McpFlowsSection
          flowsMCPData={flowsMCPData}
          handleOnNewValue={handleOnNewValue}
        />

        <div className="flex flex-1 flex-col gap-4 overflow-hidden">
          {ENABLE_MCP_COMPOSER && (
            <McpAuthSection
              hasAuthentication={hasAuthentication}
              composerUrlData={composerUrlData}
              isLoading={isLoading}
              currentAuthSettings={currentAuthSettings}
              setAuthModalOpen={setAuthModalOpen}
            />
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
              <McpJsonContent
                selectedPlatform={selectedPlatform}
                setSelectedPlatform={setSelectedPlatform}
                isDarkMode={isDarkMode}
                isCopied={isCopied}
                copyToClipboard={copyToClipboard}
                mcpJson={mcpJson}
                isAuthApiKey={isAuthApiKey}
                apiKey={apiKey}
                isGeneratingApiKey={isGeneratingApiKey}
                generateApiKey={generateApiKey}
              />
            ) : (
              <McpAutoInstallContent
                isLocalConnection={isLocalConnection}
                installedMCPData={installedMCPData}
                loadingMCP={loadingMCP}
                installClient={installClient}
                installedClients={installedClients}
              />
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
