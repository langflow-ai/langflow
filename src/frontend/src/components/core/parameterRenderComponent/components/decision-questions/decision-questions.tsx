import { cloneDeep } from "lodash";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import {
  type QuestionText,
  questionConnections,
  scapeJSONParse,
} from "@/utils/reactflowUtils";
import type { DecisionQuestionsComponentType, InputProps } from "../../types";
import DecisionQuestionsModal, {
  type DecisionQuestion,
  KINDS,
  QuestionPreview,
  questionHandleTitle,
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
  // A minimized node hides the cards and draws their handles with its others.
  const minimized = useFlowStore(
    (state) =>
      state.nodes.find((node) => node.id === nodeId)?.data.showNode === false,
  );
  const [open, setOpen] = useState(false);
  const [openAt, setOpenAt] = useState(0);
  if (!showParameter) return null;

  const questions = Array.isArray(value) ? value : [];
  const template = nodeClass?.template;
  // Each of a question's texts can be connected through its own hidden node field.
  const connectionsOf = (question: DecisionQuestion) =>
    questionConnections(question, connectionPrefix);
  const connectionOf = (question: DecisionQuestion, text: QuestionText) =>
    connectionsOf(question).find((connection) => connection.text === text)
      ?.fieldName;
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
  const isConnected = (
    question: DecisionQuestion,
    text: QuestionText = "question",
  ) => edgesInto(connectionOf(question, text)).length > 0;
  // The edit dialog and inspection panel have no canvas, so no handles.
  const drawsHandles = !editNode && !inspectionPanel && !!nodeId && !minimized;
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

  // Done applies the modal's questions, adding or removing their connection fields (and any
  // edge into a removed one) in the same node update.
  const applyQuestions = (next: DecisionQuestion[]) => {
    const nextFields = new Set(
      next.flatMap(connectionsOf).map(({ fieldName }) => fieldName),
    );
    const removed = questions
      .flatMap(connectionsOf)
      .map(({ fieldName }) => fieldName)
      .filter((field) => !nextFields.has(field));
    const added = next.flatMap((question, index) =>
      connectionsOf(question)
        .filter(({ fieldName }) => !template?.[fieldName])
        .map((connection) => ({ ...connection, number: index + 1 })),
    );
    // One snapshot before any change, so Undo restores the questions and their wiring together.
    takeSnapshot();
    const staleEdges = removed.flatMap((field) => edgesInto(field));
    if (staleEdges.length) deleteEdge(staleEdges.map((edge) => edge.id));
    if (!nodeClass || !handleNodeClass || !fieldName || !firstConnection) {
      handleOnNewValue({ value: next }, { skipSnapshot: true });
      return;
    }
    const newNodeClass = cloneDeep(nodeClass);
    // The first question's field belongs to the component class and is what new questions copy.
    for (const field of removed) {
      if (field !== `${connectionPrefix}1`) delete newNodeClass.template[field];
    }
    for (const { text, fieldName: field, number } of added) {
      newNodeClass.template[field] = {
        ...cloneDeep(firstConnection),
        name: field,
        display_name: questionHandleTitle(t, number, text),
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
        const connections = drawsHandles
          ? connectionsOf(question).filter(
              ({ fieldName }) => template?.[fieldName],
            )
          : [];
        const textConnection = connections.find(
          ({ text }) => text === "question",
        );
        const meanings = connections.filter(({ text }) => text !== "question");
        const handle = (text: QuestionText, fieldName: string) => (
          <QuestionHandle
            nodeId={nodeId!}
            fieldName={fieldName}
            field={template![fieldName]}
            title={questionHandleTitle(t, index + 1, text)}
          />
        );
        return (
          <div key={question.id ?? index} className="flex flex-col gap-1">
            {/* Spans to the node's left border, where the handle sits like any field's. */}
            <div className="relative -ml-5 pl-5">
              {textConnection &&
                handle(textConnection.text, textConnection.fieldName)}
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
            {/* A Noul migrated from the old fields keeps What Yes / No Means connectable. */}
            {meanings.map(({ text, fieldName }) => (
              <div
                key={fieldName}
                className="relative -ml-5 pl-7 text-xs text-muted-foreground"
              >
                {handle(text, fieldName)}
                {t(`decisionQuestions.${text}`)}
              </div>
            ))}
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
        <IconComponent
          name={questions.length ? "Pencil" : "Plus"}
          className="mr-1 h-4 w-4"
        />
        {t(
          questions.length
            ? "decisionQuestions.edit"
            : "decisionQuestions.addQuestions",
        )}
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
