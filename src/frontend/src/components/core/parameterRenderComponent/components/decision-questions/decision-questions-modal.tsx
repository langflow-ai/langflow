import { cloneDeep } from "lodash";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import BaseModal from "@/modals/baseModal";
import { cn } from "@/utils/utils";
import TabComponent from "../tabComponent";

export const KINDS = ["Choice", "Noul", "Score"];

type Row = { id?: string; label?: string; description?: string };

export type DecisionQuestion = {
  id?: string;
  input_field?: string;
  name?: string;
  kind?: string;
  question?: string;
  options?: Row[];
  levels?: Row[];
  yes_description?: string;
  no_description?: string;
};

// Choice keeps its options and Score its levels; the other table is kept, unused, if the type changes.
const TABLE = { Choice: "options", Score: "levels" } as const;

export const newQuestionId = () => Math.random().toString(36).slice(2, 10);

export default function DecisionQuestionsModal({
  id,
  open,
  setOpen,
  questions,
  initialIndex,
  newQuestion,
  isConnected,
  onDone,
}: {
  id: string;
  open: boolean;
  setOpen: (open: boolean) => void;
  questions: DecisionQuestion[];
  initialIndex: number;
  newQuestion?: DecisionQuestion;
  isConnected: (question: DecisionQuestion) => boolean;
  onDone: (questions: DecisionQuestion[]) => void;
}) {
  const { t } = useTranslation();
  // Edits stay here until Done; closing any other way discards them.
  const [draft, setDraft] = useState<DecisionQuestion[]>([]);
  const [selected, setSelected] = useState(0);
  // Done shows which question still needs its text.
  const [checked, setChecked] = useState(false);
  const blank = () => ({
    ...cloneDeep(newQuestion ?? {}),
    id: newQuestionId(),
  });
  useEffect(() => {
    if (open) {
      // A node with no questions opens on a new one.
      setDraft(questions.length ? cloneDeep(questions) : [blank()]);
      setSelected(initialIndex);
      setChecked(false);
    }
  }, [open]);

  const question = draft[selected];
  const needsText = (item: DecisionQuestion) =>
    !isConnected(item) && !item.question?.trim();
  const kindLabels = KINDS.map((kind) => t(`decisionQuestions.kind${kind}`));
  const table = TABLE[question?.kind as keyof typeof TABLE];
  const rows = (table && question?.[table]) ?? [];
  const update = (change: DecisionQuestion) =>
    setDraft(draft.map((q, i) => (i === selected ? { ...q, ...change } : q)));
  const setRows = (next: Row[]) => table && update({ [table]: next });
  const fieldId = (name: string) => `${id}_${name}_${selected}`;

  const addQuestion = () => {
    setDraft([...draft, blank()]);
    setSelected(draft.length);
  };
  const done = () => {
    const missing = draft.findIndex(needsText);
    if (missing !== -1) {
      setSelected(missing);
      setChecked(true);
      return;
    }
    onDone(draft);
    setOpen(false);
  };
  const deleteQuestion = () => {
    setDraft(draft.filter((_, i) => i !== selected));
    setSelected(Math.max(0, selected - 1));
  };

  return (
    <BaseModal open={open} setOpen={setOpen} size="x-large">
      <BaseModal.Header description={t("decisionQuestions.modalDescription")}>
        {t("decisionQuestions.modalTitle")}
      </BaseModal.Header>
      <BaseModal.Content>
        <div className="flex h-full min-h-0 gap-6">
          <div className="flex w-64 shrink-0 flex-col gap-2 overflow-y-auto">
            {draft.map((item, index) => (
              <button
                key={item.id ?? index}
                type="button"
                data-testid={`${id}_modal_question_${index}`}
                aria-current={index === selected}
                onClick={() => setSelected(index)}
                className={cn(
                  "flex flex-col gap-1 rounded-md border p-3 text-left",
                  index === selected
                    ? "border-primary bg-muted"
                    : "border-border hover:bg-muted",
                )}
              >
                <span className="flex items-center gap-2">
                  <span className="truncate font-mono text-sm">
                    {item.name || `q${index + 1}`}
                  </span>
                  <Badge variant="secondaryStatic" size="tag">
                    {kindLabels[KINDS.indexOf(item.kind ?? "")] ?? item.kind}
                  </Badge>
                </span>
                <QuestionPreview
                  question={item}
                  connected={isConnected(item)}
                />
              </button>
            ))}
            <Button
              variant="outline"
              size="sm"
              data-testid={`${id}_modal_add`}
              onClick={addQuestion}
            >
              <IconComponent name="Plus" className="mr-1 h-4 w-4" />
              {t("decisionQuestions.add")}
            </Button>
          </div>
          {!question ? (
            <p className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
              {t("decisionQuestions.empty")}
            </p>
          ) : (
            <div className="flex min-w-0 flex-1 flex-col gap-5 overflow-y-auto pr-1">
              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-2">
                  <label
                    htmlFor={fieldId("name")}
                    className="text-sm font-medium"
                  >
                    {t("decisionQuestions.name")}
                  </label>
                  <Input
                    id={fieldId("name")}
                    data-testid={`${id}_modal_name`}
                    value={question.name ?? ""}
                    className="font-mono"
                    onChange={(event) => update({ name: event.target.value })}
                  />
                  <span className="text-xs text-muted-foreground">
                    {t("decisionQuestions.nameHint")}
                  </span>
                </div>
                <div className="flex flex-col gap-2">
                  <span
                    id={fieldId("kind_label")}
                    className="text-sm font-medium"
                  >
                    {t("decisionQuestions.kind")}
                  </span>
                  {/* The tabs show translated names; the value saved stays the canonical type. */}
                  <TabComponent
                    id={fieldId("kind")}
                    value={kindLabels[KINDS.indexOf(question.kind ?? "")] ?? ""}
                    options={kindLabels}
                    editNode={false}
                    disabled={false}
                    ariaLabelledBy={fieldId("kind_label")}
                    handleOnNewValue={({ value }) =>
                      update({ kind: KINDS[kindLabels.indexOf(value)] })
                    }
                  />
                  {question.kind && (
                    <span className="text-xs text-muted-foreground">
                      {t(`decisionQuestions.kind${question.kind}Hint`)}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex flex-col gap-2">
                <label
                  htmlFor={fieldId("question")}
                  className="text-sm font-medium"
                >
                  {t("decisionQuestions.question")}
                  <span className="text-destructive"> *</span>
                </label>
                {isConnected(question) ? (
                  <div
                    id={fieldId("question")}
                    className="rounded-md border border-dashed border-border p-3 text-sm text-muted-foreground"
                    data-testid={`${id}_modal_question_connected`}
                  >
                    {t("decisionQuestions.questionConnectedHint")}
                  </div>
                ) : (
                  <Textarea
                    id={fieldId("question")}
                    data-testid={`${id}_modal_question_text`}
                    value={question.question ?? ""}
                    required
                    aria-invalid={checked && needsText(question)}
                    aria-describedby={fieldId("question_error")}
                    className={cn(
                      "min-h-20",
                      checked && needsText(question) && "border-destructive",
                    )}
                    onChange={(event) =>
                      update({ question: event.target.value })
                    }
                  />
                )}
                {checked && needsText(question) && (
                  <span
                    id={fieldId("question_error")}
                    className="text-xs text-destructive"
                    data-testid={`${id}_modal_question_error`}
                  >
                    {t("decisionQuestions.questionRequired")}
                  </span>
                )}
              </div>
              {table && (
                <RowsEditor
                  id={id}
                  kind={question.kind as "Choice" | "Score"}
                  rows={rows}
                  setRows={setRows}
                />
              )}
              {question.kind === "Noul" &&
                (["yes_description", "no_description"] as const).map((key) => (
                  <div key={key} className="flex flex-col gap-2">
                    <label
                      htmlFor={fieldId(key)}
                      className="text-sm font-medium"
                    >
                      {t(`decisionQuestions.${key}`)}
                    </label>
                    <Input
                      id={fieldId(key)}
                      data-testid={`${id}_modal_${key}`}
                      value={question[key] ?? ""}
                      onChange={(event) =>
                        update({ [key]: event.target.value })
                      }
                    />
                  </div>
                ))}
            </div>
          )}
        </div>
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{
          label: t("decisionQuestions.done"),
          dataTestId: `${id}_modal_done`,
          onClick: done,
        }}
      >
        <Button
          variant="ghost"
          className="text-destructive"
          disabled={!question}
          data-testid={`${id}_modal_delete`}
          onClick={deleteQuestion}
        >
          <IconComponent name="Trash2" className="mr-1 h-4 w-4" />
          {t("decisionQuestions.delete")}
        </Button>
      </BaseModal.Footer>
    </BaseModal>
  );
}

export function QuestionPreview({
  question,
  connected,
}: {
  question: DecisionQuestion;
  connected: boolean;
}) {
  const { t } = useTranslation();
  if (connected) {
    return (
      <span className="flex items-center gap-1 text-sm text-muted-foreground">
        <IconComponent name="Link" className="h-3.5 w-3.5 shrink-0" />
        {t("decisionQuestions.questionConnected")}
      </span>
    );
  }
  if (!question.question?.trim()) return null;
  return <span className="truncate text-sm">{question.question}</span>;
}

// Options or levels: ID is the key the result uses, Label is what the model reads.
function RowsEditor({
  id,
  kind,
  rows,
  setRows,
}: {
  id: string;
  kind: "Choice" | "Score";
  rows: Row[];
  setRows: (rows: Row[]) => void;
}) {
  const { t } = useTranslation();
  const table = TABLE[kind];
  const setCell = (index: number, key: keyof Row, value: string) =>
    setRows(
      rows.map((row, i) => (i === index ? { ...row, [key]: value } : row)),
    );
  const columns = [
    ["id", t("decisionQuestions.columnId")],
    ["label", t("decisionQuestions.columnLabel")],
    ["description", t(`decisionQuestions.${table}Description`)],
  ] as const;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-medium">
          {t(`decisionQuestions.${table}`)}
        </span>
        <span className="text-xs text-muted-foreground">
          {t(`decisionQuestions.${table}Hint`)}
        </span>
      </div>
      <div className="rounded-md border border-border">
        <div className="grid grid-cols-[2rem_1fr_1fr_2fr_2rem] gap-2 border-b border-border px-3 py-2 text-xs text-muted-foreground">
          <span>#</span>
          {columns.map(([key, label]) => (
            <span key={key}>{label}</span>
          ))}
          <span />
        </div>
        {rows.map((row, index) => (
          <div
            key={index}
            className="grid grid-cols-[2rem_1fr_1fr_2fr_2rem] items-center gap-2 border-b border-border px-3 py-2"
            data-testid={`${id}_modal_row_${index}`}
          >
            <span className="text-sm text-muted-foreground">{index + 1}</span>
            {columns.map(([key, label]) => (
              <Input
                key={key}
                value={row[key] ?? ""}
                aria-label={`${label} ${index + 1}`}
                className={key === "id" ? "font-mono" : undefined}
                onChange={(event) => setCell(index, key, event.target.value)}
              />
            ))}
            <Button
              variant="ghost"
              size="iconSm"
              aria-label={t("decisionQuestions.removeRow", {
                number: index + 1,
              })}
              onClick={() => setRows(rows.filter((_, i) => i !== index))}
            >
              <IconComponent name="Trash2" className="h-4 w-4" />
            </Button>
          </div>
        ))}
        <Button
          variant="ghost"
          size="sm"
          className="m-1"
          data-testid={`${id}_modal_add_row`}
          onClick={() =>
            setRows([...rows, { id: "", label: "", description: "" }])
          }
        >
          <IconComponent name="Plus" className="mr-1 h-4 w-4" />
          {t(`decisionQuestions.${table}Add`)}
        </Button>
      </div>
    </div>
  );
}
