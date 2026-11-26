import type { Dispatch, ReactNode, SetStateAction } from "react";
import { ParameterRenderComponent } from "@/components/core/parameterRenderComponent";
import type { APIClassType, InputFieldType } from "@/types/api";
import type { FlowType } from "@/types/flow";
import type {
  LocalToolBinding,
  ProjectConfig,
  ProjectFlowBindings,
  ProjectTypeType,
} from "../../entities";
import {
  CapabilityPackPicker,
  capabilityKind,
} from "./components/capability-pack-picker";
import { HookFlowPicker } from "./components/hook-flow-picker";
import { HarnessFlowPicker } from "./components/instructions-flow-picker";
import { LocalToolReview } from "./components/local-tool-review";
import { LongTextField } from "./components/long-text-field";
import { ProjectChoiceField } from "./components/project-choice-field";
import { ProjectFlowPicker } from "./components/project-flow-picker";
import { SkillDefinitionsEditor } from "./components/skill-definitions-editor";
import { ToolPackPicker } from "./components/tool-pack-picker";
import { editorDraft } from "./editor-draft";
import type { SkillDefinition, SkillPackReference } from "./skills";
import { selectedToolPacks } from "./tool-packs";

export const PROJECT_FLOWS_WIDGET = "project_flows";
export const asStringList = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter((item): item is string => !!item) : [];

interface ProjectFieldContext {
  fieldName: string;
  field: ProjectTypeType["template"][string];
  type: ProjectTypeType;
  projectId: string;
  values: ProjectConfig;
  savedValues: ProjectConfig;
  edits: ProjectConfig;
  bindings: ProjectFlowBindings;
  flows: FlowType[];
  selectedAgent?: FlowType;
  selectedAgentId?: string;
  hasAgentPanel: boolean;
  isLoadingFlows: boolean;
  isPending: boolean;
  setEdits: Dispatch<SetStateAction<ProjectConfig>>;
  updateBinding: (name: string, value: ProjectFlowBindings[string]) => void;
  syntheticNodeClass: APIClassType;
}

/** The fixed widget vocabulary. Python types reuse these existing controls. */
export function renderProjectField({
  fieldName,
  field,
  type,
  projectId,
  values,
  savedValues,
  edits,
  bindings,
  flows,
  selectedAgent,
  selectedAgentId,
  hasAgentPanel,
  isLoadingFlows,
  isPending,
  setEdits,
  updateBinding,
  syntheticNodeClass,
}: ProjectFieldContext): ReactNode {
  const widgets: Record<string, () => ReactNode> = {
    long_text: () => (
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
            contract={field.flow_contract}
            agentId={selectedAgentId}
            value={
              Array.isArray(bindings[fieldName])
                ? undefined
                : bindings[fieldName]
            }
            initialValue={String(values[fieldName] ?? "")}
            onOpen={() => editorDraft.keep(projectId, edits)}
            disabled={isPending}
            onChange={(binding) => updateBinding(fieldName, binding)}
          />
        )}
      </>
    ),
    skill_definitions: () => (
      <SkillDefinitionsEditor
        projectId={projectId}
        value={(values[fieldName] ?? []) as SkillDefinition[]}
        disabled={isPending}
        onOpen={() => editorDraft.keep(projectId, edits)}
        onChange={(next) =>
          setEdits((current) => ({
            ...current,
            [fieldName]: next,
          }))
        }
      />
    ),
    skill_pack_refs: () => (
      <CapabilityPackPicker
        kind={capabilityKind(field.references)}
        projectId={projectId}
        value={(values[fieldName] ?? []) as SkillPackReference[]}
        disabled={isPending || (hasAgentPanel && !selectedAgent)}
        onOpen={() => editorDraft.keep(projectId, edits)}
        onChange={(next) =>
          setEdits((current) => ({
            ...current,
            [fieldName]: next,
          }))
        }
      />
    ),
    project_refs: () => (
      <ToolPackPicker
        projectId={projectId}
        references={field.references}
        agent={selectedAgent}
        value={selectedToolPacks(values[fieldName])}
        saved={selectedToolPacks(savedValues[fieldName])}
        disabled={isPending}
        onOpen={() => editorDraft.keep(projectId, edits)}
        onChange={(next) =>
          setEdits((current) => ({
            ...current,
            [fieldName]: next,
          }))
        }
      />
    ),
    hook_flows: () => (
      <HookFlowPicker
        key={`${projectId}:${selectedAgentId}`}
        projectId={projectId}
        fieldName={fieldName}
        contract={field.flow_contract}
        agentId={selectedAgentId}
        value={Array.isArray(bindings[fieldName]) ? bindings[fieldName] : []}
        disabled={isPending}
        onChange={(next) => updateBinding(fieldName, next)}
        onOpen={() => editorDraft.keep(projectId, edits)}
      />
    ),
    project_flows: () => (
      <>
        <ProjectFlowPicker
          helpText={!hasAgentPanel ? field.info : undefined}
          flows={flows.filter((flow) => flow.id !== selectedAgentId)}
          isLoading={isLoadingFlows}
          disabled={isPending || (hasAgentPanel && !selectedAgent)}
          value={asStringList(values[fieldName])}
          onChange={(picked) =>
            setEdits((current) => ({
              ...current,
              [fieldName]: picked,
            }))
          }
        />
        {type.panels?.includes("local-tool-review") && (
          <LocalToolReview
            projectId={projectId}
            selected={asStringList(values[fieldName])}
            value={
              values.tool_bindings as
                | Record<string, LocalToolBinding>
                | undefined
            }
            saved={
              savedValues.tool_bindings as
                | Record<string, LocalToolBinding>
                | undefined
            }
            disabled={isPending}
            onOpen={() => editorDraft.keep(projectId, edits)}
            onChange={(next) =>
              setEdits((current) => ({
                ...current,
                tool_bindings: next,
              }))
            }
          />
        )}
      </>
    ),
  };
  const key = field.renders ?? "";
  if (Object.hasOwn(widgets, key)) return widgets[key]();
  return field.option_labels ? (
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
          contract={field.flow_contract}
          agentId={selectedAgentId}
          value={
            Array.isArray(bindings[fieldName]) ? undefined : bindings[fieldName]
          }
          initialConfig={Object.fromEntries(
            (field.flow_contract?.binding?.initial_config_fields ?? []).map(
              (name) => [name, values[name]],
            ),
          )}
          disabled={isPending}
          onChange={(binding) => updateBinding(fieldName, binding)}
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
  );
}
