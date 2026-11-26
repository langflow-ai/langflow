import "./harness-form.css";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { ParameterRenderComponent } from "@/components/core/parameterRenderComponent";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useGetProjectFlowsQuery } from "@/controllers/API/queries/folders/use-get-project-flows";
import { useGetProjectTypesQuery } from "@/controllers/API/queries/folders/use-get-project-types";
import { usePatchFolders } from "@/controllers/API/queries/folders/use-patch-folders";
import { getCustomParameterTitle } from "@/customization/components/custom-parameter";
import useAlertStore from "@/stores/alertStore";
import type { APIClassType, InputFieldType } from "@/types/api";
import type {
  CompactionBinding,
  ContextBinding,
  ProjectConfig,
  ProjectFlowBindings,
  ProjectSaveResult,
  ProjectTypeType,
} from "../../entities";
import {
  AgentFlowPicker,
  agentCandidates,
  defaultAgent,
} from "./components/agent-flow-picker";
import { HarnessSummary } from "./components/harness-summary";
import { HookFlowPicker } from "./components/hook-flow-picker";
import { HarnessFlowPicker } from "./components/instructions-flow-picker";
import { LongTextField } from "./components/long-text-field";
import { ProjectChoiceField } from "./components/project-choice-field";
import { ProjectFlowPicker } from "./components/project-flow-picker";

import { editorDraft } from "./editor-draft";
import { isProjectFieldVisible } from "./field-visibility";
import { validCompactionThreshold, validFlowTimeout } from "./flow-binding";

interface HarnessPageProps {
  projectId: string;
  projectType: string;
  projectConfig?: ProjectConfig | null;
}

/** Widgets this page supplies, for fields the canvas renderer cannot serve well. */
const PROJECT_FLOWS_WIDGET = "project_flows";
const LONG_TEXT_WIDGET = "long_text";

const asStringList = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter((item): item is string => !!item) : [];

/**
 * The form a typed project renders: the harness builder.
 *
 * Everything on this page comes from `GET /api/v1/projects/types`. The type declares its fields
 * in the same shape as a component's template, so they render through the field renderer the
 * canvas already uses, and it declares the sections those fields are grouped into, so the shape
 * of the form belongs to the type rather than to this file. The one field the canvas has no
 * widget for, "which flows here can the agent call", asks for this page's own picker by name.
 *
 * Saving writes `project_config`, which records what the user picked.
 */
const HarnessPage = ({
  projectId,
  projectType,
  projectConfig,
}: HarnessPageProps) => {
  const { t } = useTranslation();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const { data: projectTypes, isLoading } = useGetProjectTypesQuery();
  const {
    data: projectFlows,
    isLoading: isLoadingFlows,
    isError: isFlowsError,
    refetch: refetchFlows,
  } = useGetProjectFlowsQuery({ projectId });
  const { mutate: patchProject, isPending } = usePatchFolders();

  const type = useMemo(
    () => projectTypes?.find((candidate) => candidate.name === projectType),
    [projectTypes, projectType],
  );

  // What the form starts from: the saved config where there is one, the type's own defaults
  // everywhere else. A project saved before a field existed still renders that field.
  const savedValues = useMemo(() => {
    const template = type?.template ?? {};
    const defaults = Object.fromEntries(
      Object.entries(template).map(([fieldName, field]) => [
        fieldName,
        projectConfig && fieldName in projectConfig
          ? projectConfig[fieldName]
          : field?.value,
      ]),
    );
    if (projectType === "agent-harness" && projectConfig?.agent_flow_id) {
      defaults.agent_flow_id = projectConfig.agent_flow_id;
    }
    if (projectConfig?.flow_bindings)
      defaults.flow_bindings = projectConfig.flow_bindings;
    return defaults;
  }, [type, projectConfig, projectType]);

  const [edits, setEdits] = useState<ProjectConfig>(() =>
    editorDraft.get(projectId),
  );
  useEffect(() => {
    editorDraft.clear(projectId);
  }, [projectId]);
  useEffect(() => {
    const field = new URLSearchParams(window.location.search).get("field");
    if (field && type?.template[field]) {
      const target = document.getElementById(`harness-field-${field}`);
      target?.scrollIntoView?.({ block: "center" });
      target?.focus();
    }
  }, [type]);
  const [lastSave, setLastSave] = useState<ProjectSaveResult | null>(null);
  const values = { ...savedValues, ...edits };
  const bindings = (values.flow_bindings ?? {}) as ProjectFlowBindings;
  const bindingsValid = Object.entries(bindings).every(([field, binding]) =>
    Array.isArray(binding)
      ? binding.every((hook) => validFlowTimeout(hook.timeout_seconds ?? 10))
      : field === "compaction" && binding
        ? validFlowTimeout(
            (binding as CompactionBinding).timeout_seconds ?? 60,
          ) &&
          validCompactionThreshold(
            (binding as CompactionBinding).trigger_tokens ?? 8000,
          )
        : (field !== "context_strategy" && field !== "tool_policy") ||
          !binding ||
          validFlowTimeout(
            (binding as ContextBinding).timeout_seconds ??
              (field === "tool_policy" ? 10 : 30),
          ),
  );
  const updateBinding = (
    fieldName: string,
    binding: ProjectFlowBindings[string],
  ) => {
    setEdits((current) => {
      const next = {
        ...((current.flow_bindings ??
          savedValues.flow_bindings ??
          {}) as ProjectFlowBindings),
      };
      if (binding) next[fieldName] = binding;
      else delete next[fieldName];
      return { ...current, flow_bindings: next };
    });
  };
  const isDirty = Object.keys(edits).some(
    (fieldName) =>
      JSON.stringify(edits[fieldName]) !==
      JSON.stringify(savedValues[fieldName]),
  );

  // ParameterRenderComponent takes the component a field belongs to. A project form has no node,
  // so the type itself stands in: the widgets that read it want a template and a label.
  const syntheticNodeClass: APIClassType = useMemo(
    () => ({
      description: type?.description ?? "",
      display_name: type?.display_name ?? "",
      documentation: "",
      icon: type?.icon,
      template: (type?.template ?? {}) as APIClassType["template"],
    }),
    [type],
  );

  // One group per section, in the order the type's fields first name them.
  const sections = useMemo(() => {
    const grouped = new Map<
      string,
      [string, ProjectTypeType["template"][string]][]
    >();
    for (const [fieldName, field] of Object.entries(type?.template ?? {})) {
      if (!isProjectFieldVisible(field, values)) continue;
      const section = (field as { section?: string })?.section ?? "";
      if (!grouped.has(section)) grouped.set(section, []);
      grouped.get(section)?.push([fieldName, field]);
    }
    return [...grouped.entries()];
  }, [type, values]);

  const toolsFieldName = useMemo(
    () =>
      Object.entries(type?.template ?? {}).find(
        ([, field]) =>
          (field as { renders?: string })?.renders === PROJECT_FLOWS_WIDGET,
      )?.[0],
    [type],
  );

  const modelFieldName = useMemo(
    () =>
      Object.entries(type?.template ?? {}).find(
        ([, field]) => field?.type === "model",
      )?.[0],
    [type],
  );

  const flows = projectFlows ?? [];
  const selectedAgentId =
    typeof values.agent_flow_id === "string"
      ? values.agent_flow_id
      : defaultAgent(flows)?.id;
  const candidates = agentCandidates(flows);
  const selectedAgent = candidates.find((flow) => flow.id === selectedAgentId);
  const agentSelectionRequired =
    projectType === "agent-harness" &&
    !selectedAgent &&
    (!!selectedAgentId || candidates.length > 1);
  const pickedToolIds = toolsFieldName
    ? asStringList(values[toolsFieldName])
    : [];
  const toolFlows = flows.filter((flow) => pickedToolIds.includes(flow.id));

  // The summary gives the model and the tools their own treatment, so the remaining rows are
  // everything else the form holds, read back as plain text.
  const summaryDetails = useMemo(
    () =>
      Object.entries(type?.template ?? {})
        .filter(
          ([fieldName, field]) =>
            fieldName !== toolsFieldName &&
            fieldName !== modelFieldName &&
            isProjectFieldVisible(field, values) &&
            // A long free-text field says nothing useful at a glance.
            !field?.multiline,
        )
        .map(([fieldName, field]) => {
          const binding = bindings[fieldName];
          return {
            name: fieldName,
            label: field?.display_name ?? fieldName,
            value:
              (field as { renders?: string }).renders === "hook_flows"
                ? t("harness.hookCount", {
                    count: Array.isArray(bindings[fieldName])
                      ? bindings[fieldName].length
                      : 0,
                  })
                : binding && !Array.isArray(binding)
                  ? t("harness.flowImplementation", {
                      name:
                        flows.find((flow) => flow.id === binding.flow_id)
                          ?.name ?? t("harness.boundFlowUnavailable"),
                    })
                  : values[fieldName] === undefined || values[fieldName] === ""
                    ? "—"
                    : (field.option_labels?.[String(values[fieldName])] ??
                      String(values[fieldName])),
          };
        }),
    [type, toolsFieldName, modelFieldName, values, bindings, flows, t],
  );

  const handleSave = () => {
    if (!bindingsValid) return;
    patchProject(
      // Only the config. Sending the name or the description here would let a half-loaded page
      // overwrite either of them with a stale value.
      {
        folderId: projectId,
        data: {
          project_config: {
            ...values,
            ...(projectType === "agent-harness" && selectedAgentId
              ? { agent_flow_id: selectedAgentId }
              : {}),
          },
        },
      },
      {
        onSuccess: (result) => {
          setEdits({});
          setLastSave(result);
          // Say what the save did, not just that it happened: these values are copied onto the
          // components of the project's flows, and that is the part worth seeing.
          const flowsUpdated = (result as { flows_updated?: number })
            ?.flows_updated;
          setSuccessData({
            title: flowsUpdated
              ? t("harness.savedToFlows", { count: flowsUpdated })
              : t("harness.saved"),
          });
        },
        onError: (error) => {
          const detail = (
            error as { response?: { data?: { detail?: unknown } } }
          )?.response?.data?.detail;
          setErrorData({
            title: t("harness.saveFailed"),
            list: typeof detail === "string" ? [detail] : undefined,
          });
        },
      },
    );
  };

  if (isLoading) {
    return (
      <div className="mt-4 flex flex-col gap-4" data-testid="harness-loading">
        {[0, 1].map((card) => (
          <div
            key={card}
            className="flex flex-col gap-4 rounded-xl border border-border bg-background p-4"
          >
            <Skeleton className="h-3 w-24" />
            <Skeleton className="h-20 w-full" />
          </div>
        ))}
      </div>
    );
  }

  if (!type) {
    return (
      <div className="pt-24 text-center text-sm text-secondary-foreground">
        {t("harness.unknownType", { projectType })}
      </div>
    );
  }

  if (Object.keys(type.template).length === 0) {
    return (
      <div className="pt-24 text-center text-sm text-secondary-foreground">
        {t("harness.noFields")}
      </div>
    );
  }

  if (isFlowsError) {
    return (
      <div role="alert" className="flex flex-col items-start gap-3 py-6">
        <p className="text-sm">{t("harness.flowsLoadFailed")}</p>
        <Button variant="outline" size="sm" onClick={() => void refetchFlows()}>
          {t("harness.retryFlows")}
        </Button>
      </div>
    );
  }

  return (
    <div
      className="harness-form mx-auto flex min-h-0 w-full min-w-0 max-w-6xl flex-col"
      data-testid="harness-page"
    >
      {/* Stays in reach: the form runs past the viewport once a few sections are filled in. */}
      <div className="sticky top-0 z-10 -mt-4 flex flex-wrap items-center justify-between gap-3 border-b border-border bg-background py-4">
        <div className="flex min-w-0 items-start gap-2.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-muted">
            <ForwardedIconComponent
              name={type.icon || "Bot"}
              aria-hidden="true"
              className="h-4 w-4 text-foreground"
            />
          </div>
          <div className="flex min-w-0 flex-col">
            <h1 className="text-lg font-semibold">{type.display_name}</h1>
            <p className="text-sm text-muted-foreground">
              {t("harness.configureAgent")}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-3">
          {isDirty && (
            <span
              className="text-xs text-muted-foreground"
              data-testid="harness-unsaved"
            >
              {t("harness.unsaved")}
            </span>
          )}
          <Button
            size="sm"
            data-testid="harness-save-btn"
            onClick={handleSave}
            disabled={
              !isDirty ||
              isPending ||
              isLoadingFlows ||
              agentSelectionRequired ||
              !bindingsValid
            }
            loading={isPending}
          >
            {t("harness.save")}
          </Button>
        </div>
      </div>

      <div className="grid min-w-0 items-start gap-8 py-6 xl:grid-cols-[minmax(0,1fr)_280px]">
        <fieldset
          disabled={isPending}
          inert={isPending}
          className="flex min-w-0 flex-col gap-8 border-0 p-0"
        >
          {projectType === "agent-harness" && (
            <AgentFlowPicker
              flows={flows}
              value={selectedAgentId}
              isLoading={isLoadingFlows}
              disabled={isPending}
              onChange={(id) =>
                setEdits((current) => ({
                  ...current,
                  agent_flow_id: id,
                  ...(toolsFieldName
                    ? {
                        [toolsFieldName]: pickedToolIds.filter(
                          (toolId) => toolId !== id,
                        ),
                      }
                    : {}),
                }))
              }
            />
          )}
          {sections.map(([section, fields]) => (
            <section
              key={section || "fields"}
              data-testid={`harness-section-${section || "fields"}`}
              className="flex min-w-0 flex-col gap-5 border-b border-border/60 pb-8 last:border-0"
            >
              {section && (
                <h2 className="text-base font-semibold">{section}</h2>
              )}

              {fields.map(([fieldName, field]) => (
                <div
                  key={fieldName}
                  id={`harness-field-${fieldName}`}
                  tabIndex={-1}
                  className="flex min-w-0 flex-col gap-2"
                  data-testid={`harness-field-${fieldName}`}
                >
                  {(field?.display_name ?? fieldName) !== section && (
                    <div className="flex items-center gap-2">
                      {getCustomParameterTitle({
                        title: field?.display_name ?? fieldName,
                        // No canvas node stands behind this form.
                        nodeId: "",
                        isFlexView: false,
                        required: field?.required ?? false,
                        requiredText: t("field.required"),
                      })}
                    </div>
                  )}

                  {(field as { renders?: string })?.renders ===
                  LONG_TEXT_WIDGET ? (
                    <>
                      {!bindings[fieldName] && (
                        <LongTextField
                          name={fieldName}
                          label={field?.display_name ?? fieldName}
                          disabled={isPending}
                          value={String(values[fieldName] ?? "")}
                          placeholder={field?.placeholder ?? ""}
                          onChange={(next) =>
                            setEdits((current) => ({
                              ...current,
                              [fieldName]: next,
                            }))
                          }
                        />
                      )}
                      {(field as { supports_flow_binding?: boolean })
                        .supports_flow_binding && (
                        <HarnessFlowPicker
                          key={`${projectId}:${selectedAgentId}:${fieldName}`}
                          projectId={projectId}
                          fieldName={fieldName}
                          agentId={selectedAgentId}
                          value={
                            Array.isArray(bindings[fieldName])
                              ? undefined
                              : bindings[fieldName]
                          }
                          initialValue={String(values[fieldName] ?? "")}
                          onOpen={() => editorDraft.keep(projectId, edits)}
                          disabled={isPending}
                          onChange={(binding) =>
                            updateBinding(fieldName, binding)
                          }
                        />
                      )}
                    </>
                  ) : (field as { renders?: string })?.renders ===
                    "hook_flows" ? (
                    <HookFlowPicker
                      key={`${projectId}:${selectedAgentId}`}
                      projectId={projectId}
                      fieldName={fieldName}
                      agentId={selectedAgentId}
                      value={
                        Array.isArray(bindings[fieldName])
                          ? bindings[fieldName]
                          : []
                      }
                      disabled={isPending}
                      onChange={(next) => updateBinding(fieldName, next)}
                      onOpen={() => editorDraft.keep(projectId, edits)}
                    />
                  ) : (field as { renders?: string })?.renders ===
                    PROJECT_FLOWS_WIDGET ? (
                    <ProjectFlowPicker
                      flows={flows.filter(
                        (flow) => flow.id !== selectedAgentId,
                      )}
                      isLoading={isLoadingFlows}
                      disabled={
                        isPending ||
                        (projectType === "agent-harness" && !selectedAgent)
                      }
                      value={asStringList(values[fieldName])}
                      onChange={(picked) =>
                        setEdits((current) => ({
                          ...current,
                          [fieldName]: picked,
                        }))
                      }
                    />
                  ) : field.option_labels ? (
                    <>
                      {!bindings[fieldName] && (
                        <ProjectChoiceField
                          name={fieldName}
                          label={field.display_name ?? fieldName}
                          options={field.option_labels}
                          value={String(values[fieldName] ?? "")}
                          disabled={isPending}
                          onChange={(value) =>
                            setEdits((current) => ({
                              ...current,
                              [fieldName]: value,
                            }))
                          }
                        />
                      )}
                      {field.supports_flow_binding && (
                        <HarnessFlowPicker
                          key={`${projectId}:${selectedAgentId}:${fieldName}`}
                          projectId={projectId}
                          fieldName={fieldName}
                          agentId={selectedAgentId}
                          value={
                            Array.isArray(bindings[fieldName])
                              ? undefined
                              : bindings[fieldName]
                          }
                          initialConfig={
                            fieldName === "compaction"
                              ? {
                                  compaction_trigger_tokens:
                                    values.compaction_trigger_tokens,
                                  compaction_keep_messages:
                                    values.compaction_keep_messages,
                                }
                              : fieldName === "tool_policy"
                                ? { tool_policy: values.tool_policy }
                                : {
                                    context_strategy: values.context_strategy,
                                    context_turns: values.context_turns,
                                  }
                          }
                          disabled={isPending}
                          onChange={(binding) =>
                            updateBinding(fieldName, binding)
                          }
                          onOpen={() => editorDraft.keep(projectId, edits)}
                        />
                      )}
                    </>
                  ) : (
                    <ParameterRenderComponent
                      handleOnNewValue={(changes) =>
                        setEdits((current) => ({
                          ...current,
                          [fieldName]: (changes as { value: unknown })?.value,
                        }))
                      }
                      name={fieldName}
                      // The widgets that write to the flow store check for a node id first, and
                      // an empty one makes them skip that and report the value here instead.
                      nodeId=""
                      templateData={field as Partial<InputFieldType>}
                      templateValue={values[fieldName] ?? ""}
                      editNode={false}
                      showParameter={true}
                      inspectionPanel={false}
                      handleNodeClass={() => {}}
                      nodeClass={syntheticNodeClass}
                      // Canvas widgets use `disabled` for a connected input and may clear
                      // its value. The fieldset handles temporary form save restrictions.
                      disabled={false}
                      placeholder={field?.placeholder ?? ""}
                      isToolMode={false}
                      // No flow is open here, so provider credentials scope to the project.
                      providerScope={{ projectId }}
                    />
                  )}
                  {field.info &&
                    !bindings[fieldName] &&
                    !(field as { renders?: string }).renders && (
                      <p className="text-xs leading-relaxed text-muted-foreground">
                        {field.info}
                      </p>
                    )}
                </div>
              ))}
            </section>
          ))}
        </fieldset>

        <div className="flex min-w-0 flex-col gap-4 xl:sticky xl:top-32">
          <HarnessSummary
            displayName={type.display_name}
            icon={type.icon}
            model={modelFieldName ? values[modelFieldName] : undefined}
            toolFlows={toolFlows}
            details={summaryDetails}
            agentFlow={selectedAgent}
          />
          <div className="rounded-lg bg-muted/50 p-4 text-sm text-muted-foreground">
            {t("harness.canvasEditsKept")}
          </div>
          {lastSave && (
            <div
              role="status"
              data-testid="harness-save-result"
              className="flex flex-col gap-2 border-t border-border pt-4 text-sm"
            >
              <p className="font-medium">
                {lastSave.flows_updated
                  ? t("harness.savedToFlows", { count: lastSave.flows_updated })
                  : t("harness.saved")}
              </p>
              {!!lastSave.fields_skipped && (
                <p>
                  {t("harness.fieldsKept", { count: lastSave.fields_skipped })}
                </p>
              )}
              {!!lastSave.flows_locked && (
                <p>
                  {t("harness.lockedFlows", { count: lastSave.flows_locked })}
                </p>
              )}
              {!!Object.keys(lastSave.restore_version_ids ?? {}).length && (
                <p className="text-muted-foreground">
                  {t("harness.restorePointCreated")}
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default HarnessPage;
