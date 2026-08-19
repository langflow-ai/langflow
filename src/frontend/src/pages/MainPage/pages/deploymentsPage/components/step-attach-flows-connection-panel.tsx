import { memo, useId } from "react";
import { useTranslation } from "react-i18next";
import InputComponent from "@/components/core/parameterRenderComponent/components/inputComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/utils/utils";
import type { ConnectionItem, EnvVarEntry } from "../types";
import { handleTabListKeyDown } from "../utils/tab-keyboard-navigation";
import { ConnectionSearchList } from "./connection-search-list";

export type ConnectionTab = "available" | "create";

const CONNECTION_TABS: ConnectionTab[] = ["available", "create"];

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
  const { t } = useTranslation();
  const connectionNameId = useId();
  const connectionNameErrorId = useId();

  return (
    <>
      <div className="border-b border-border p-4 text-sm text-muted-foreground">
        {t("deployments.selectOrCreateConnection")}
      </div>
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden px-4 py-4">
        <div className="shrink-0 rounded-xl border border-border bg-muted p-1">
          <div
            role="tablist"
            aria-label={t("deployments.connectionTabsAriaLabel")}
            className="grid grid-cols-2"
          >
            {CONNECTION_TABS.map((tab, index) => (
              <button
                key={tab}
                id={`connection-tab-${tab}`}
                type="button"
                role="tab"
                aria-selected={connectionTab === tab}
                aria-controls={`connection-panel-${tab}`}
                tabIndex={connectionTab === tab ? 0 : -1}
                onClick={() => onTabChange(tab)}
                onKeyDown={(event) =>
                  handleTabListKeyDown(
                    event,
                    index,
                    CONNECTION_TABS,
                    onTabChange,
                    "connection-tab",
                  )
                }
                className={cn(
                  "min-w-0 rounded-lg px-3 py-2 text-sm transition-colors",
                  connectionTab === tab
                    ? "bg-background"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {tab === "available"
                  ? t("deployments.availableConnections")
                  : t("deployments.createConnection")}
              </button>
            ))}
          </div>
        </div>

        {/* Tab content */}
        <div
          id="connection-panel-available"
          role="tabpanel"
          aria-labelledby="connection-tab-available"
          className="mt-4 flex-1 overflow-x-hidden overflow-y-auto"
          hidden={connectionTab !== "available"}
        >
          <div className="min-w-0 space-y-3">
            <ConnectionSearchList
              connections={connections}
              selectedConnections={selectedConnections}
              onToggleConnection={onToggleConnection}
              onSwitchToCreate={() => onTabChange("create")}
            />
          </div>
        </div>
        <div
          id="connection-panel-create"
          role="tabpanel"
          aria-labelledby="connection-tab-create"
          className="mt-4 flex-1 overflow-x-hidden overflow-y-auto"
          hidden={connectionTab !== "create"}
        >
          <div className="flex flex-col gap-4">
            <div className="flex flex-col">
              <label
                htmlFor={connectionNameId}
                className="pb-2 text-sm font-medium"
              >
                {t("deployments.connectionNameLabel")}
                <span className="text-destructive" aria-hidden="true">
                  *
                </span>
              </label>
              <Input
                id={connectionNameId}
                placeholder={t("deployments.placeholderConnectionName")}
                className="bg-muted"
                value={newConnectionName}
                aria-required="true"
                aria-invalid={isDuplicateName}
                aria-describedby={
                  isDuplicateName ? connectionNameErrorId : undefined
                }
                onChange={(e) =>
                  onNameChange(e.target.value.replace(/[^a-zA-Z0-9_ ]/g, ""))
                }
              />
              {isDuplicateName && (
                <span
                  id={connectionNameErrorId}
                  className="pt-1 text-xs text-destructive"
                >
                  {t("deployments.connectionNameExists")}
                </span>
              )}
            </div>
            <div className="flex flex-col">
              <span className="pb-2 text-sm font-medium">
                {t("deployments.environmentVariables")}
                <span className="text-destructive" aria-hidden="true">
                  *
                </span>
              </span>
              {detectedVarCount > 0 && (
                <p className="mb-2 text-xs text-muted-foreground">
                  {t("deployments.variablesAutoDetected", {
                    count: detectedVarCount,
                  })}
                </p>
              )}
              <div className="space-y-2">
                {envVars.map((envVar) => (
                  <div key={envVar.id} className="grid grid-cols-2 gap-2">
                    <Input
                      placeholder={t("deployments.placeholderKey")}
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
                      placeholder={t("deployments.placeholderValue")}
                      value={envVar.value}
                      options={globalVariableOptions}
                      optionsPlaceholder={t("deployments.globalVariables")}
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
                  {t("deployments.addVariable")}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Footer buttons */}
        <div className="flex min-w-0 flex-wrap items-center gap-3 pt-4">
          <Button
            variant="outline"
            onClick={onChangeFlow}
            data-testid="connection-change-flow"
            className="min-w-0 max-w-[11rem] whitespace-normal text-center"
          >
            {t("deployments.changeFlow")}
          </Button>
          <Button
            variant="outline"
            onClick={onSkipConnection}
            data-testid="connection-skip"
            className="min-w-0 max-w-[8rem] whitespace-normal text-center"
          >
            {t("deployments.skip")}
          </Button>
          {connectionTab === "available" ? (
            <Button
              className="ml-auto w-full text-center whitespace-normal sm:w-auto sm:min-w-[220px] sm:whitespace-nowrap"
              disabled={selectedConnections.size === 0}
              onClick={onAttachConnection}
              data-testid="connection-attach"
            >
              {t("deployments.attachConnectionToFlow")}
            </Button>
          ) : (
            <Button
              className="ml-auto w-full text-center whitespace-normal sm:w-auto sm:min-w-[220px] sm:whitespace-nowrap"
              disabled={newConnectionName.trim() === "" || isDuplicateName}
              onClick={onCreateConnection}
              data-testid="connection-create"
            >
              {t("deployments.createConnection")}
            </Button>
          )}
        </div>
      </div>
    </>
  );
});
