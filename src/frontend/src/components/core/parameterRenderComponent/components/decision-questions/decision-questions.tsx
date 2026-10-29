import { cloneDeep } from "lodash";
import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { APITemplateType } from "@/types/api";
import { scapeJSONParse } from "@/utils/reactflowUtils";
import type { DecisionQuestionsComponentType, InputProps } from "../../types";
import TableNodeComponent from "../TableNodeComponent";
import TabComponent from "../tabComponent";
import QuestionHandle from "./question-handle";

const KINDS = ["Choice", "Boolean", "Score"];

export type DecisionQuestion = {
  id?: string;
  name?: string;
  kind?: string;
  question?: string;
  options?: Record<string, unknown>[];
  levels?: Record<string, unknown>[];
  yes_description?: string;
  no_description?: string;
};

export default function DecisionQuestionsComponent({
  id,
  value,
  handleOnNewValue,
  disabled,
  editNode,
  columns,
  newQuestion,
  connectionPrefix,
  fieldName,
  nodeId,
  nodeClass,
  handleNodeClass,
  inspectionPanel = false,
  showParameter = true,
}: InputProps<DecisionQuestion[], DecisionQuestionsComponentType>) {
  const { t } = useTranslation();
  const edges = useFlowStore((state) => state.edges);
  const deleteEdge = useFlowStore((state) => state.deleteEdge);
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
  if (!showParameter) return null;

  const questions = Array.isArray(value) ? value : [];
  const save = (next: DecisionQuestion[]) => handleOnNewValue({ value: next });
  // Each question's text can be connected through its own hidden node field.
  const template = nodeClass?.template;
  const connectionOf = (question: DecisionQuestion) =>
    connectionPrefix && question.id
      ? `${connectionPrefix}${question.id}`
      : undefined;
  const firstConnection =
    connectionPrefix && template?.[`${connectionPrefix}1`];
  const edgesInto = (field?: string) =>
    edges.filter(
      (edge) =>
        field &&
        edge.target === nodeId &&
        edge.targetHandle &&
        scapeJSONParse(edge.targetHandle).fieldName === field,
    );
  // Adding or removing a question also adds or removes its connection field, in one node update.
  const saveWithFields = (
    next: DecisionQuestion[],
    changeFields: (template: APITemplateType) => void,
  ) => {
    if (!nodeClass || !handleNodeClass || !fieldName) return save(next);
    takeSnapshot();
    const newNodeClass = cloneDeep(nodeClass);
    changeFields(newNodeClass.template);
    newNodeClass.template[fieldName].value = next;
    handleNodeClass(newNodeClass);
  };
  const addQuestion = () => {
    const question: DecisionQuestion = cloneDeep(newQuestion ?? {});
    if (!firstConnection) return save([...questions, question]);
    question.id = Math.random().toString(36).slice(2, 10);
    const field = connectionOf(question)!;
    saveWithFields([...questions, question], (fields) => {
      fields[field] = {
        ...cloneDeep(firstConnection),
        name: field,
        display_name: t("decisionQuestions.title", {
          number: questions.length + 1,
        }),
        value: "",
      };
    });
  };
  const removeQuestion = (index: number) => {
    const next = questions.filter((_, i) => i !== index);
    const field = connectionOf(questions[index]);
    const connected = edgesInto(field);
    if (connected.length) deleteEdge(connected.map((edge) => edge.id));
    // The first question's field belongs to the component class, so it stays.
    if (!field || field === `${connectionPrefix}1`) return save(next);
    saveWithFields(next, (fields) => {
      delete fields[field];
    });
  };
  const update = (index: number, change: DecisionQuestion) =>
    save(questions.map((q, i) => (i === index ? { ...q, ...change } : q)));
  const inputClass = editNode ? "input-edit-node" : "";
  // The tabs show translated names; the value saved stays the canonical type.
  const kindLabels = KINDS.map((kind) => t(`decisionQuestions.kind${kind}`));

  return (
    <div className="flex w-full flex-col gap-3">
      {questions.map((question, index) => {
        const number = index + 1;
        const title = t("decisionQuestions.title", { number });
        const kindLabelId = `${id}_kind_label_${index}`;
        const connection = connectionOf(question);
        const isConnected = edgesInto(connection).length > 0;
        // The edit dialog and inspection panel have no canvas, so no handle.
        const showHandle =
          !editNode &&
          !inspectionPanel &&
          !!nodeId &&
          !!template?.[connection ?? ""];
        // One table per type, edited in the same modal the Options field uses.
        const table = { Choice: "options", Score: "levels" }[
          question.kind ?? ""
        ] as "options" | "levels" | undefined;
        return (
          <fieldset
            key={index}
            className="flex flex-col gap-2 rounded-md border border-border p-3"
            data-testid={`${id}_question_${index}`}
          >
            <legend className="sr-only">{title}</legend>
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">{title}</span>
              <Button
                variant="ghost"
                size="iconSm"
                disabled={disabled || questions.length === 1}
                aria-label={t("decisionQuestions.remove", { number })}
                data-testid={`${id}_remove_${index}`}
                onClick={() => removeQuestion(index)}
              >
                <IconComponent name="Trash2" className="h-4 w-4" />
              </Button>
            </div>
            <Input
              data-testid={`${id}_name_${index}`}
              value={question.name ?? ""}
              placeholder={t("decisionQuestions.namePlaceholder", { number })}
              aria-label={t("decisionQuestions.name", { number })}
              className={inputClass}
              disabled={disabled}
              onChange={(event) => update(index, { name: event.target.value })}
            />
            <span id={kindLabelId} className="sr-only">
              {t("decisionQuestions.kind", { number })}
            </span>
            <TabComponent
              id={`${id}_kind_${index}`}
              value={kindLabels[KINDS.indexOf(question.kind ?? "")] ?? ""}
              options={kindLabels}
              editNode={editNode}
              disabled={disabled}
              ariaLabelledBy={kindLabelId}
              handleOnNewValue={({ value }) =>
                update(index, { kind: KINDS[kindLabels.indexOf(value)] })
              }
            />
            {/* Spans to the node's left border, where the handle sits like any field's. */}
            <div className="relative -ml-[33px] pl-[33px]">
              {showHandle && connection && (
                <QuestionHandle
                  nodeId={nodeId!}
                  fieldName={connection}
                  field={template![connection]}
                  title={title}
                />
              )}
              {isConnected ? (
                <div
                  className="flex h-9 items-center rounded-md border border-dashed border-border px-3 text-sm text-muted-foreground"
                  data-testid={`${id}_question_connected_${index}`}
                >
                  {t("decisionQuestions.questionConnected")}
                </div>
              ) : (
                <Input
                  data-testid={`${id}_question_text_${index}`}
                  value={question.question ?? ""}
                  placeholder={t("decisionQuestions.questionPlaceholder")}
                  aria-label={t("decisionQuestions.question", { number })}
                  className={inputClass}
                  disabled={disabled}
                  onChange={(event) =>
                    update(index, { question: event.target.value })
                  }
                />
              )}
            </div>
            {table && (
              <TableNodeComponent
                id={`${id}_${table}_${index}`}
                value={question[table] ?? []}
                columns={columns}
                editNode={editNode}
                disabled={disabled}
                tableTitle={t(`decisionQuestions.${table}`)}
                description={t(`decisionQuestions.${table}Info`)}
                trigger_text={t(`decisionQuestions.${table}Edit`)}
                handleOnNewValue={({ value }) =>
                  update(index, { [table]: value })
                }
              />
            )}
            {question.kind === "Boolean" &&
              (["yes_description", "no_description"] as const).map((key) => (
                <Input
                  key={key}
                  data-testid={`${id}_${key}_${index}`}
                  value={question[key] ?? ""}
                  placeholder={t(`decisionQuestions.${key}`)}
                  aria-label={t(`decisionQuestions.${key}`)}
                  className={inputClass}
                  disabled={disabled}
                  onChange={(event) =>
                    update(index, { [key]: event.target.value })
                  }
                />
              ))}
          </fieldset>
        );
      })}
      <Button
        variant="outline"
        size="sm"
        disabled={disabled}
        data-testid={`${id}_add`}
        onClick={addQuestion}
      >
        <IconComponent name="Plus" className="mr-1 h-4 w-4" />
        {t("decisionQuestions.add")}
      </Button>
    </div>
  );
}
