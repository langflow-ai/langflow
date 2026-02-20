import { type Dispatch, type SetStateAction } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Input } from "@/components/ui/input";
import type { ConfigMode, KeyFormat } from "../constants";

type EnvVar = { key: string; value: string };

type StepConfigurationProps = {
  configMode: ConfigMode;
  setConfigMode: (v: ConfigMode) => void;
  configName: string;
  setConfigName: (v: string) => void;
  keyFormat: KeyFormat;
  setKeyFormat: (v: KeyFormat) => void;
  envVars: EnvVar[];
  setEnvVars: Dispatch<SetStateAction<EnvVar[]>>;
};

export const StepConfiguration = ({
  configMode,
  setConfigMode,
  configName,
  setConfigName,
  keyFormat,
  setKeyFormat,
  envVars,
  setEnvVars,
}: StepConfigurationProps) => (
  <div className="flex h-full flex-col gap-4 overflow-y-auto">
    <div>
      <h3 className="text-base font-semibold">Deployment Configuration</h3>
      <p className="mt-1 text-sm text-muted-foreground">
        Choose how to configure environment variables. The Config name becomes
        the Connection AppID in watsonx Orchestrate.
      </p>
    </div>
    <div className="grid grid-cols-3 gap-2">
      {(
        [
          {
            mode: "reuse" as ConfigMode,
            label: "Reuse existing Config",
            description: "Use a Config that's already been created",
            warn: false,
          },
          {
            mode: "create" as ConfigMode,
            label: "Create new Config",
            description: "Define a new Config with environment variables",
            warn: false,
          },
          {
            mode: "modify" as ConfigMode,
            label: "Modify selected Config",
            description:
              "Edit an existing Config (may affect other deployments)",
            warn: true,
          },
        ] as const
      ).map(({ mode, label, description, warn }) => (
        <button
          key={mode}
          onClick={() => setConfigMode(mode)}
          className={`flex flex-col gap-0.5 rounded-lg border bg-background p-4 text-left transition-colors ${
            configMode === mode
              ? "border-primary"
              : "border-border hover:border-muted-foreground"
          }`}
        >
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold">{label}</span>
            {warn && (
              <ForwardedIconComponent
                name="TriangleAlert"
                className="h-4 w-4 text-yellow-400"
              />
            )}
          </div>
          <span className="text-sm text-muted-foreground">{description}</span>
        </button>
      ))}
    </div>
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-medium">
        Config Name (AppID) <span className="text-destructive">*</span>
      </label>
      <Input
        placeholder="e.g., SALES_BOT_PROD"
        value={configName}
        onChange={(e) => setConfigName(e.target.value)}
      />
      <p className="text-xs text-muted-foreground">
        This name becomes the Connection AppID in watsonx Orchestrate. Use
        uppercase letters, numbers, and underscores only.
      </p>
    </div>
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-medium">Variable Key Format</label>
      <div className="flex gap-2">
        {(
          [
            { id: "assisted" as KeyFormat, label: "Assisted Prefix" },
            { id: "auto" as KeyFormat, label: "Auto-Prefix" },
            { id: "manual" as KeyFormat, label: "Manual" },
          ] as const
        ).map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setKeyFormat(id)}
            className={`rounded-md border px-3 py-1.5 text-sm transition-colors ${
              keyFormat === id
                ? "border-foreground bg-background font-semibold text-foreground"
                : "border-border bg-background text-muted-foreground hover:border-muted-foreground"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
    <div className="flex min-h-0 flex-1 flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium">
          Environment Variables <span className="text-destructive">*</span>
        </label>
        <button
          onClick={() =>
            setEnvVars((prev) => [...prev, { key: "", value: "" }])
          }
          className="flex items-center gap-1 text-sm text-foreground hover:text-muted-foreground"
        >
          <ForwardedIconComponent name="Plus" className="h-4 w-4" />
          Add Variable
        </button>
      </div>
      <div className="flex h-full flex-col rounded-lg border border-border bg-background">
        {envVars.length === 0 ? (
          <p className="flex h-full min-h-[80px] items-center justify-center text-sm text-muted-foreground">
            No variables yet. Click "Add Variable" to get started.
          </p>
        ) : (
          <div className="flex flex-col divide-y divide-border">
            {envVars.map((v, i) => (
              <div key={i} className="flex items-center gap-2 p-2">
                <Input
                  placeholder="KEY"
                  value={v.key}
                  onChange={(e) =>
                    setEnvVars((prev) =>
                      prev.map((x, j) =>
                        j === i ? { ...x, key: e.target.value } : x,
                      ),
                    )
                  }
                  className="flex-1"
                />
                <Input
                  placeholder="VALUE"
                  value={v.value}
                  onChange={(e) =>
                    setEnvVars((prev) =>
                      prev.map((x, j) =>
                        j === i ? { ...x, value: e.target.value } : x,
                      ),
                    )
                  }
                  className="flex-1"
                />
                <button
                  onClick={() =>
                    setEnvVars((prev) => prev.filter((_, j) => j !== i))
                  }
                  className="text-muted-foreground hover:text-destructive"
                >
                  <ForwardedIconComponent name="X" className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  </div>
);
