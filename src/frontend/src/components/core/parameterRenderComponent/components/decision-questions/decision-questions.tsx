import { cloneDeep } from "lodash";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { scapeJSONParse } from "@/utils/reactflowUtils";
import type { DecisionQuestionsComponentType, InputProps } from "../../types";
import DecisionQuestionsModal, {
  type DecisionQuestion,
  KINDS,
  QuestionPreview,
} from "./decision-questions-modal";
import QuestionHandle from "./question-handle";

export type { DecisionQuestion };

// One compact row per question on the node; questions are edited in the modal.
export default function DecisionQuestionsComponent({
  id,
  value,
  handleOnNewValue,
  disabled,
  editNode,
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
  const [open, setOpen] = useState(false);
  const [openAt, setOpenAt] = useState(0);
  if (!showParameter) return null;

  const questions = Array.isArray(value) ? value : [];
  const template = nodeClass?.template;
  // Each question's text can be connected through its own hidden node field.
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
  const isConnected = (question: DecisionQuestion) =>
    edgesInto(connectionOf(question)).length > 0;
  // The edit dialog and inspection panel have no canvas, so no handles.
  const drawsHandles = !editNode && !inspectionPanel && !!nodeId;
  const kindLabel = (kind?: string) =>
    KINDS.includes(kind ?? "") ? t(`decisionQuestions.kind${kind}`) : kind;
  const summary = (question: DecisionQuestion) =>
    question.kind === "Choice"
      ? t("decisionQuestions.optionCount", {
          count: question.options?.length ?? 0,
        })
      : question.kind === "Score"
        ? t("decisionQuestions.levelCount", {
            count: question.levels?.length ?? 0,
          })
        : t("decisionQuestions.yesNo");

  // Done applies the modal's questions, adding or removing each question's connection field
  // (and any edge into a removed one) in the same node update.
  const applyQuestions = (next: DecisionQuestion[]) => {
    const kept = new Set(next.map((question) => question.id));
    const removed = questions
      .filter((question) => !kept.has(question.id))
      .map(connectionOf)
      // The first question's field belongs to the component class, so it stays.
      .filter((field) => field && field !== `${connectionPrefix}1`);
    const added = next
      .map(connectionOf)
      .filter((field) => field && !template?.[field]);
    const staleEdges = removed.flatMap((field) => edgesInto(field));
    if (staleEdges.length) deleteEdge(staleEdges.map((edge) => edge.id));
    if (!nodeClass || !handleNodeClass || !fieldName || !firstConnection) {
      handleOnNewValue({ value: next });
      return;
    }
    takeSnapshot();
    const newNodeClass = cloneDeep(nodeClass);
    for (const field of removed) delete newNodeClass.template[field!];
    for (const field of added) {
      newNodeClass.template[field!] = {
        ...cloneDeep(firstConnection),
        name: field,
        display_name: t("decisionQuestions.title", {
          number: next.findIndex((q) => connectionOf(q) === field) + 1,
        }),
        value: "",
      };
    }
    newNodeClass.template[fieldName].value = next;
    handleNodeClass(newNodeClass);
  };
  const openEditor = (index: number) => {
    setOpenAt(index);
    setOpen(true);
  };

  return (
    <div className="flex w-full flex-col gap-2">
      {questions.map((question, index) => {
        const connection = connectionOf(question);
        return (
          // Spans to the node's left border, where the handle sits like any field's.
          <div key={question.id ?? index} className="relative -ml-5 pl-5">
            {drawsHandles && connection && template?.[connection] && (
              <QuestionHandle
                nodeId={nodeId!}
                fieldName={connection}
                field={template[connection]}
                title={t("decisionQuestions.title", { number: index + 1 })}
              />
            )}
            <button
              type="button"
              disabled={disabled}
              data-testid={`${id}_question_${index}`}
              aria-label={t("decisionQuestions.editQuestion", {
                number: index + 1,
              })}
              onClick={() => openEditor(index)}
              className="flex w-full flex-col gap-1 rounded-md border border-border p-2 text-left hover:bg-muted disabled:pointer-events-none"
            >
              <span className="flex w-full items-center gap-2">
                <span className="truncate font-mono text-sm">
                  {question.name || `q${index + 1}`}
                </span>
                <Badge variant="secondaryStatic" size="tag">
                  {kindLabel(question.kind)}
                </Badge>
                <span className="ml-auto shrink-0 text-xs text-muted-foreground">
                  {summary(question)}
                </span>
              </span>
              <QuestionPreview
                question={question}
                connected={isConnected(question)}
              />
            </button>
          </div>
        );
      })}
      <Button
        variant="outline"
        size="sm"
        disabled={disabled}
        data-testid={`${id}_edit`}
        onClick={() => openEditor(0)}
      >
        <IconComponent name="Pencil" className="mr-1 h-4 w-4" />
        {t("decisionQuestions.edit")}
      </Button>
      <DecisionQuestionsModal
        id={id}
        open={open}
        setOpen={setOpen}
        questions={questions}
        initialIndex={openAt}
        newQuestion={newQuestion}
        isConnected={isConnected}
        onDone={applyQuestions}
      />
    </div>
  );
}
