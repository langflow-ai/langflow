import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { toSpaceCase } from "@/utils/stringManipulation";
import { cn } from "@/utils/utils";
import { autoInstallers } from "../utils/mcpServerUtils";

interface McpAutoInstallContentProps {
  isLocalConnection: boolean;
  installedMCPData?: Array<{ name?: string; available?: boolean }>;
  loadingMCP: string[];
  installClient: (name: string, title?: string) => void;
  installedClients?: string[];
}

export const McpAutoInstallContent = ({
  isLocalConnection,
  installedMCPData,
  loadingMCP,
  installClient,
  installedClients,
}: McpAutoInstallContentProps) => (
  <div className="flex flex-col gap-1 mt-4">
    {!isLocalConnection && (
      <div className="mb-2 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-950 dark:text-amber-200">
        <div className="flex items-center gap-3">
          <ForwardedIconComponent
            name="AlertTriangle"
            className="h-4 w-4 shrink-0"
          />
          <span>
            One-click install is disabled because the Langflow server is not
            running on your local machine. Use the JSON tab to configure your
            client manually.
          </span>
        </div>
      </div>
    )}
    {autoInstallers.map((installer) => (
      <ShadTooltip
        key={installer.name}
        content={
          !installedMCPData?.find((client) => client.name === installer.name)
            ?.available
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
            onClick={() => installClient(installer.name, installer.title)}
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
                  loadingMCP.includes(installer.name) && "animate-spin",
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
);
