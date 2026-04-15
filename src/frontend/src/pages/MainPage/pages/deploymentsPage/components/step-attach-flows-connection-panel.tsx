import { memo } from "react";
import InputComponent from "@/components/core/parameterRenderComponent/components/inputComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/utils/utils";
import type { ConnectionItem, EnvVarEntry } from "../types";
import { ConnectionSearchList } from "./connection-search-list";

export type ConnectionTab = "available" | "create";

export const ConnectionPanel = memo(function ConnectionPanel({
  connectionTab,
  onTabChange,
  connections,
  selectedConnections,
  onToggleConnection,
  newConnectionName,
  onNameChange,
  envVars,
  detectedVarCount,
  globalVariableOptions,
  onEnvVarChange,
  onEnvVarSelectGlobalVar,
  onAddEnvVar,
  onChangeFlow,
  onSkipConnection,
  onAttachConnection,
  onCreateConnection,
  isDuplicateName,
}: {
  connectionTab: ConnectionTab;
  onTabChange: (tab: ConnectionTab) => void;
  connections: ConnectionItem[];
  selectedConnections: Set<string>;
  onToggleConnection: (id: string) => void;
  newConnectionName: string;
  onNameChange: (v: string) => void;
  envVars: EnvVarEntry[];
  detectedVarCount: number;
  globalVariableOptions: string[];
  onEnvVarChange: (id: string, field: "key" | "value", val: string) => void;
  onEnvVarSelectGlobalVar: (id: string, selected: string) => void;
  onAddEnvVar: () => void;
  onChangeFlow: () => void;
  onSkipConnection: () => void;
  onAttachConnection: () => void;
  onCreateConnection: () => void;
  isDuplicateName?: boolean;
}) {
  return (
    <>
      <div className="border-b border-border p-4 text-sm text-muted-foreground">
        Select or Create New Connection
      </div>
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden px-4 py-4">
        {/* Tab toggle */}
        <div className="shrink-0 rounded-xl border border-border bg-muted p-1">
          <div className="grid grid-cols-2">
            {(["available", "create"] as const).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => onTabChange(tab)}
                className={cn(
                  "min-w-0 rounded-lg px-3 py-2 text-sm transition-colors",
                  connectionTab === tab
                    ? "bg-background"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {tab === "available"
                  ? "Available Connections"
                  : "Create Connection"}
              </button>
            ))}
          </div>
        </div>

        {/* Tab content */}
        <div
          className="mt-4 flex-1 overflow-x-hidden overflow-y-auto"
          key={connectionTab}
        >
          {connectionTab === "available" ? (
            <div className="min-w-0 space-y-3">
              <ConnectionSearchList
                connections={connections}
                selectedConnections={selectedConnections}
                onToggleConnection={onToggleConnection}
                onSwitchToCreate={() => onTabChange("create")}
              />
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              <div className="flex flex-col">
                <span className="pb-2 text-sm font-medium">
                  Connection Name<span className="text-destructive">*</span>
                </span>
                <Input
                  placeholder="e.g., SALES_BOT_PROD"
                  className="bg-muted"
                  value={newConnectionName}
                  onChange={(e) =>
                    onNameChange(e.target.value.replace(/[^a-zA-Z0-9_ ]/g, ""))
                  }
                />
                {isDuplicateName && (
                  <span className="pt-1 text-xs text-destructive">
                    A connection with this name already exists.
                  </span>
                )}
              </div>
              <div className="flex flex-col">
                <span className="pb-2 text-sm font-medium">
                  Environment Variables
                  <span className="text-destructive">*</span>
                </span>
                {detectedVarCount > 0 && (
                  <p className="mb-2 text-xs text-muted-foreground">
                    {detectedVarCount} variable
                    {detectedVarCount > 1 ? "s" : ""} auto-detected from the
                    selected flow version.
                  </p>
                )}
                <div className="space-y-2">
                  {envVars.map((envVar) => (
                    <div key={envVar.id} className="grid grid-cols-2 gap-2">
                      <Input
                        placeholder="Key"
                        className="bg-muted"
                        value={envVar.key}
                        onChange={(e) =>
                          onEnvVarChange(envVar.id, "key", e.target.value)
                        }
                      />
                      <InputComponent
                        nodeStyle
                        password
                        id={`env-val-${envVar.id}`}
                        placeholder="Value"
                        value={envVar.value}
                        options={globalVariableOptions}
                        optionsPlaceholder="Global Variables"
                        optionsIcon="Globe"
                        selectedOption={envVar.globalVar ? envVar.value : ""}
                        setSelectedOption={(sel) =>
                          onEnvVarSelectGlobalVar(envVar.id, sel)
                        }
                        onChange={(text) =>
                          onEnvVarChange(envVar.id, "value", text)
                        }
                      />
                    </div>
                  ))}
                  <button
                    type="button"
                    onClick={onAddEnvVar}
                    className="text-sm text-muted-foreground hover:text-foreground"
                  >
                    + Add variable
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer buttons */}
        <div className="flex min-w-0 flex-wrap items-center gap-3 pt-4">
          <Button
            variant="outline"
            onClick={onChangeFlow}
            data-testid="connection-change-flow"
          >
            Change Flow
          </Button>
          <Button
            variant="outline"
            onClick={onSkipConnection}
            data-testid="connection-skip"
          >
            Skip
          </Button>
          {connectionTab === "available" ? (
            <Button
              className="ml-auto w-full text-center whitespace-normal sm:w-auto sm:min-w-[220px] sm:whitespace-nowrap"
              disabled={selectedConnections.size === 0}
              onClick={onAttachConnection}
              data-testid="connection-attach"
            >
              Attach Connection to Flow
            </Button>
          ) : (
            <Button
              className="ml-auto w-full text-center whitespace-normal sm:w-auto sm:min-w-[220px] sm:whitespace-nowrap"
              disabled={newConnectionName.trim() === "" || isDuplicateName}
              onClick={onCreateConnection}
              data-testid="connection-create"
            >
              Create Connection
            </Button>
          )}
        </div>
      </div>
    </>
  );
});
