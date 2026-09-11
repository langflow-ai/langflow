import { useMemo, useState } from "react";
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
import type { ProjectConfig } from "../../entities";
import { HarnessSummary } from "./components/harness-summary";
import { LongTextField } from "./components/long-text-field";
import { ProjectFlowPicker } from "./components/project-flow-picker";

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
  const { data: projectFlows, isLoading: isLoadingFlows } =
    useGetProjectFlowsQuery({ projectId });
  const { mutate: patchProject, isPending } = usePatchFolders();

  const type = useMemo(
    () => projectTypes?.find((candidate) => candidate.name === projectType),
    [projectTypes, projectType],
  );

  // What the form starts from: the saved config where there is one, the type's own defaults
  // everywhere else. A project saved before a field existed still renders that field.
  const savedValues = useMemo(() => {
    const template = type?.template ?? {};
    return Object.fromEntries(
      Object.entries(template).map(([fieldName, field]) => [
        fieldName,
        projectConfig && fieldName in projectConfig
          ? projectConfig[fieldName]
          : field?.value,
      ]),
    );
  }, [type, projectConfig]);

  const [edits, setEdits] = useState<ProjectConfig>({});
  const values = { ...savedValues, ...edits };
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
    const grouped = new Map<string, [string, Partial<InputFieldType>][]>();
    for (const [fieldName, field] of Object.entries(type?.template ?? {})) {
      const section = (field as { section?: string })?.section ?? "";
      if (!grouped.has(section)) grouped.set(section, []);
      grouped.get(section)?.push([fieldName, field]);
    }
    return [...grouped.entries()];
  }, [type]);

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
            // A long free-text field says nothing useful at a glance.
            !field?.multiline,
        )
        .map(([fieldName, field]) => ({
          name: fieldName,
          label: field?.display_name ?? fieldName,
          value:
            values[fieldName] === undefined || values[fieldName] === ""
              ? "—"
              : String(values[fieldName]),
        })),
    [type, toolsFieldName, modelFieldName, values],
  );

  const handleSave = () => {
    patchProject(
      // Only the config. Sending the name or the description here would let a half-loaded page
      // overwrite either of them with a stale value.
      { folderId: projectId, data: { project_config: values } },
      {
        onSuccess: () => {
          setEdits({});
          setSuccessData({ title: t("harness.saved") });
        },
        onError: () => {
          setErrorData({ title: t("harness.saveFailed") });
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

  return (
    <div className="flex min-h-0 flex-col" data-testid="harness-page">
      {/* Stays in reach: the form runs past the viewport once a few sections are filled in. */}
      <div className="sticky top-0 z-10 -mt-4 flex items-start justify-between gap-4 border-b border-border bg-background pb-3 pt-4">
        <div className="flex min-w-0 items-start gap-2.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-muted">
            <ForwardedIconComponent
              name={type.icon || "Bot"}
              aria-hidden="true"
              className="h-4 w-4 text-foreground"
            />
          </div>
          <div className="flex min-w-0 flex-col">
            <span className="text-sm font-semibold">{type.display_name}</span>
            <p className="text-xs text-muted-foreground">{type.description}</p>
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
            disabled={!isDirty || isPending}
            loading={isPending}
          >
            {t("harness.save")}
          </Button>
        </div>
      </div>

      <div className="grid items-start gap-6 py-6 xl:grid-cols-[minmax(0,1fr)_300px]">
        <div className="flex min-w-0 flex-col gap-4">
          {sections.map(([section, fields]) => (
            <section
              key={section || "fields"}
              data-testid={`harness-section-${section || "fields"}`}
              className="flex flex-col gap-4 rounded-xl border border-border bg-background p-4"
            >
              {section && (
                <h3 className="text-xxs font-semibold uppercase tracking-wider text-muted-foreground/70">
                  {section}
                </h3>
              )}

              {fields.map(([fieldName, field]) => (
                <div
                  key={fieldName}
                  className="flex flex-col gap-1.5"
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
                    <LongTextField
                      name={fieldName}
                      value={String(values[fieldName] ?? "")}
                      placeholder={field?.placeholder ?? ""}
                      onChange={(next) =>
                        setEdits((current) => ({
                          ...current,
                          [fieldName]: next,
                        }))
                      }
                    />
                  ) : (field as { renders?: string })?.renders ===
                    PROJECT_FLOWS_WIDGET ? (
                    <ProjectFlowPicker
                      flows={flows}
                      isLoading={isLoadingFlows}
                      value={asStringList(values[fieldName])}
                      onChange={(picked) =>
                        setEdits((current) => ({
                          ...current,
                          [fieldName]: picked,
                        }))
                      }
                    />
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
                      disabled={false}
                      placeholder={field?.placeholder ?? ""}
                      isToolMode={false}
                      // No flow is open here, so provider credentials scope to the project.
                      providerScope={{ projectId }}
                    />
                  )}
                </div>
              ))}
            </section>
          ))}
        </div>

        <HarnessSummary
          className="xl:sticky xl:top-20"
          displayName={type.display_name}
          icon={type.icon}
          model={modelFieldName ? values[modelFieldName] : undefined}
          toolFlows={toolFlows}
          details={summaryDetails}
        />
      </div>
    </div>
  );
};

export default HarnessPage;
