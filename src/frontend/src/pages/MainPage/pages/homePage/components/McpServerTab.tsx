import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";

import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import type { MCPTransport } from "@/controllers/API/queries/mcp/use-patch-install-mcp";
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
  const { t } = useTranslation();
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
    isLocalConnection ? "auto-install" : "json",
  );
  const [selectedTransport, setSelectedTransport] =
    useState<MCPTransport>("streamablehttp");
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
  } = useMcpServer({
    projectId,
    folderName,
    selectedPlatform,
    selectedTransport,
  });

  return (
    <div>
      <div className="flex justify-between gap-4 items-start">
        <div>
          <div className="pb-2 font-medium" data-testid="mcp-server-title">
            {t("mcp.serverTitle")}
          </div>
          <div className="pb-4 text-mmd text-muted-foreground">
            {t("mcp.serverDescription")}
            <a
              className="text-accent-pink-foreground"
              href="https://docs.langflow.org/mcp-server"
              target="_blank"
              rel="noreferrer"
            >
              {" "}
              {t("mcp.serverGuideLink")}
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
              {[
                { id: "auto-install", label: t("mcp.autoInstall") },
                { id: "json", label: "JSON" },
              ].map((item) => (
                <Button
                  unstyled
                  key={item.id}
                  className={`flex h-6 flex-row items-end gap-2 text-nowrap border-b-2 border-border border-b-transparent !py-1 font-medium ${
                    selectedMode === item.id
                      ? "border-b-2 border-black dark:border-b-white"
                      : "text-muted-foreground hover:text-foreground"
                  } px-3 py-2 text-[13px]`}
                  onClick={() => setSelectedMode(item.id)}
                >
                  <span>{item.label}</span>
                </Button>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-4 rounded-md border border-dashed border-border p-4">
            {hasOAuthError ? (
              <div className="p-4 bg-accent-red-subtle border border-accent-red-border rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <ForwardedIconComponent
                    name="AlertTriangle"
                    className="h-4 w-4 text-accent-red-foreground"
                  />
                  <span className="font-medium text-accent-red-foreground">
                    {t("mcp.configError")}
                  </span>
                </div>
                <p className="text-mmd text-accent-red-foreground">
                  {composerUrlData?.error_message}
                </p>
                <p className="text-sm text-muted-foreground mt-2">
                  {t("mcp.configErrorFix")}
                </p>
              </div>
            ) : selectedMode === "json" ? (
              <McpJsonContent
                selectedPlatform={selectedPlatform}
                setSelectedPlatform={setSelectedPlatform}
                selectedTransport={selectedTransport}
                setSelectedTransport={setSelectedTransport}
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
