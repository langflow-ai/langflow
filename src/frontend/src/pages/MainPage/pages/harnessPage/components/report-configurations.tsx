import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import type { AgentConfiguration } from "@/controllers/API/queries/folders/use-project-reports";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { ProjectChoiceField } from "./project-choice-field";

const bindingLabels: Record<string, string> = {
  system_prompt: "harness.instructionsContract",
  hooks: "harness.hookContract",
  context_strategy: "harness.contextContract",
  compaction: "harness.compactionContract",
  tool_policy: "harness.permissionContract",
};

export function ReportConfigurations({
  configurations,
  onOpen,
}: {
  configurations: AgentConfiguration[];
  onOpen?: () => void;
}) {
  const { t } = useTranslation();
  const navigate = useCustomNavigate();
  const [selected, setSelected] = useState(configurations.length - 1);
  const configuration =
    configurations[Math.max(0, Math.min(selected, configurations.length - 1))];
  return (
    <section
      className="mt-8 space-y-3 border-t border-border pt-4"
      aria-label={t("runConfig.title")}
    >
      <h3 className="text-sm font-semibold">{t("runConfig.title")}</h3>
      {!configuration ? (
        <p className="text-xs text-muted-foreground">{t("runConfig.legacy")}</p>
      ) : (
        <>
          <p className="text-xs text-muted-foreground">{t("runConfig.help")}</p>
          {configurations.length > 1 && (
            <ProjectChoiceField
              name="report-configuration"
              className="h-10"
              label={t("runConfig.select")}
              value={String(
                Math.max(0, Math.min(selected, configurations.length - 1)),
              )}
              onChange={(value) => setSelected(Number(value))}
              options={Object.fromEntries(
                configurations.map((item, index) => [
                  String(index),
                  `${t("runConfig.record", { number: index + 1 })} · ${new Date(item.captured_at).toLocaleString()}`,
                ]),
              )}
            />
          )}
          <p className="break-words text-sm">
            <span className="font-medium">{t("harness.summaryModel")}:</span>{" "}
            {configuration.model.name}
          </p>
          <details className="text-xs">
            <summary className="cursor-pointer font-medium">
              {t("runConfig.inspect")}
            </summary>
            <div className="mt-4 space-y-5">
              <div>
                <h4 className="mb-2 font-medium">{t("runConfig.prompt")}</h4>
                <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-md bg-muted p-3 font-sans leading-relaxed">
                  {configuration.system_prompt}
                </pre>
              </div>
              <JsonRecord
                title={t("runConfig.parameters")}
                value={configuration.model}
              />
              <JsonRecord
                title={t("runConfig.runtime")}
                value={configuration.runtime}
              />
              <dl className="grid grid-cols-2 gap-2">
                {[
                  [t("runConfig.history"), configuration.history_messages],
                  [
                    t("runConfig.loadedHistory"),
                    configuration.loaded_history_messages,
                  ],
                  [t("runConfig.toolRetries"), configuration.tool_retry_count],
                ].map(([label, value]) => (
                  <div key={label}>
                    <dt className="text-muted-foreground">{label}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
              <div className="space-y-3">
                <h4 className="font-medium">{t("harness.summaryTools")}</h4>
                {!configuration.tools.length && (
                  <p className="text-muted-foreground">
                    {t("runConfig.empty")}
                  </p>
                )}
                {configuration.tools.map((tool) => (
                  <details
                    key={tool.name}
                    className="rounded-md border border-border p-3"
                  >
                    <summary className="cursor-pointer break-words font-medium">
                      {tool.name}
                    </summary>
                    <p className="my-2 break-words text-muted-foreground">
                      {tool.description}
                    </p>
                    <JsonRecord
                      title={t("runConfig.toolContract")}
                      value={tool}
                    />
                  </details>
                ))}
              </div>
              <div className="space-y-3">
                <h4 className="font-medium">{t("runConfig.bindings")}</h4>
                {!Object.values(configuration.flow_bindings).some((value) =>
                  Array.isArray(value) ? value.length : value,
                ) && (
                  <p className="text-muted-foreground">
                    {t("runConfig.empty")}
                  </p>
                )}
                {Object.entries(configuration.flow_bindings).flatMap(
                  ([field, value]) =>
                    (Array.isArray(value) ? value : value ? [value] : []).map(
                      (binding, index) => (
                        <div
                          key={`${field}-${index}`}
                          className="space-y-2 rounded-md border border-border p-3"
                        >
                          <JsonRecord
                            title={t(bindingLabels[field] ?? field)}
                            value={binding}
                          />
                          <Button
                            size="sm"
                            variant="link"
                            onClick={() => {
                              onOpen?.();
                              navigate(
                                `/flow/${encodeURIComponent(binding.flow_id)}`,
                              );
                            }}
                          >
                            {t("toolPacks.openFlow")}
                          </Button>
                        </div>
                      ),
                    ),
                )}
              </div>
              <JsonRecord
                title={t("runConfig.identity")}
                value={{
                  revision: configuration.revision,
                  captured_at: configuration.captured_at,
                  flow_id: configuration.flow_id,
                  agent_node_id: configuration.agent_node_id,
                  flow_revision: configuration.flow_revision,
                  component_revision: configuration.component_revision,
                }}
              />
            </div>
          </details>
        </>
      )}
    </section>
  );
}

function JsonRecord({ title, value }: { title: string; value: unknown }) {
  return (
    <div className="space-y-2">
      <h4 className="font-medium">{title}</h4>
      <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-all rounded-md bg-muted p-3 font-mono text-xs">
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  );
}
