import { memo, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import InputComponent from "@/components/core/parameterRenderComponent/components/inputComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/utils/utils";
import type { ConnectionItem, EnvVarEntry } from "../types";
import { CheckboxSelectItem } from "./radio-select-item";

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
  const { t } = useTranslation();
  const [searchQuery, setSearchQuery] = useState("");
  const filteredConnections = useMemo(() => {
    // Sort newly created connections to the top
    const sorted = [...connections].sort((a, b) => {
      if (a.isNew && !b.isNew) return -1;
      if (!a.isNew && b.isNew) return 1;
      return 0;
    });
    if (!searchQuery.trim()) return sorted;
    const q = searchQuery.toLowerCase();
    return sorted.filter(
      (c) => c.name.toLowerCase().includes(q) || c.id.toLowerCase().includes(q),
    );
  }, [connections, searchQuery]);

  return (
    <>
      <div className="border-b border-border p-4 text-sm text-muted-foreground">
        {t("deployments.selectOrCreateConnection")}
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
                  ? t("deployments.availableConnections")
                  : t("deployments.createConnection")}
              </button>
            ))}
          </div>
        </div>

        {/* Tab content */}
        <div className="mt-4 flex-1 overflow-x-hidden overflow-y-auto">
          {connectionTab === "available" ? (
            <div className="min-w-0 space-y-3">
              {connections.length === 0 ? (
                <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
                  <ForwardedIconComponent
                    name="PlugZap"
                    className="h-8 w-8 text-muted-foreground/50"
                  />
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">
                      {t("deployments.noConnectionsYet")}
                    </p>
                    <p className="mt-0.5 text-xs text-muted-foreground/70">
                      {t("deployments.noConnectionsDescription")}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => onTabChange("create")}
                    className="text-xs font-medium text-primary hover:underline"
                  >
                    {t("deployments.createFirstConnection")}
                  </button>
                </div>
              ) : (
                <>
                  <div className="min-w-0">
                    <Input
                      icon="Search"
                      placeholder={t("deployments.placeholderSearchConnections")}
                      className="bg-muted"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                    />
                  </div>
                  {filteredConnections.length === 0 ? (
                    <p className="py-6 text-center text-sm text-muted-foreground">
                      {t("deployments.noConnectionsMatch", { query: searchQuery })}
                    </p>
                  ) : (
                    filteredConnections.map((conn) => (
                      <CheckboxSelectItem
                        key={conn.id}
                        value={conn.id}
                        checked={selectedConnections.has(conn.id)}
                        onChange={() => onToggleConnection(conn.id)}
                        data-testid={`connection-item-${conn.id}`}
                      >
                        <div className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-medium leading-tight">
                            {conn.name}
                          </span>
                        </div>
                      </CheckboxSelectItem>
                    ))
                  )}
                </>
              )}
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              <div className="flex flex-col">
                <span className="pb-2 text-sm font-medium">
                  {t("deployments.connectionNameLabel")}<span className="text-destructive">*</span>
                </span>
                <Input
                  placeholder={t("deployments.placeholderConnectionName")}
                  className="bg-muted"
                  value={newConnectionName}
                  onChange={(e) =>
                    onNameChange(e.target.value.replace(/[^a-zA-Z0-9_ ]/g, ""))
                  }
                />
                {isDuplicateName && (
                  <span className="pt-1 text-xs text-destructive">
                    {t("deployments.connectionNameExists")}
                  </span>
                )}
              </div>
              <div className="flex flex-col">
                <span className="pb-2 text-sm font-medium">
                  {t("deployments.environmentVariables")}
                  <span className="text-destructive">*</span>
                </span>
                {detectedVarCount > 0 && (
                  <p className="mb-2 text-xs text-muted-foreground">
                    {t("deployments.variablesAutoDetected", { count: detectedVarCount })}
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
          )}
        </div>

        {/* Footer buttons */}
        <div className="flex min-w-0 flex-wrap items-center gap-3 pt-4">
          <Button
            variant="outline"
            onClick={onChangeFlow}
            data-testid="connection-change-flow"
          >
            {t("deployments.changeFlow")}
          </Button>
          <Button
            variant="outline"
            onClick={onSkipConnection}
            data-testid="connection-skip"
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
