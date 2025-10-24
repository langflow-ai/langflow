import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import type { AuthSettingsType } from "@/types/mcp";
import { AUTH_METHODS } from "@/utils/mcpUtils";
import { cn } from "@/utils/utils";

interface McpAuthSectionProps {
  hasAuthentication: boolean;
  composerUrlData?: { error_message?: string };
  isLoading: boolean;
  currentAuthSettings?: AuthSettingsType;
  setAuthModalOpen: (open: boolean) => void;
}

export const McpAuthSection = ({
  hasAuthentication,
  composerUrlData,
  isLoading,
  currentAuthSettings,
  setAuthModalOpen,
}: McpAuthSectionProps) => (
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
              className={cn("h-4 w-4 shrink-0", isLoading && "animate-spin")}
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
      <ForwardedIconComponent name="Fingerprint" className="h-4 w-4 shrink-0" />
      {hasAuthentication ? "Edit Auth" : "Add Auth"}
    </Button>
  </div>
);
