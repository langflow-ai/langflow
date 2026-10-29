import { cloneDeep } from "lodash";
import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { DecisionQuestionsComponentType, InputProps } from "../../types";
import TableNodeComponent from "../TableNodeComponent";
import TabComponent from "../tabComponent";

const KINDS = ["Choice", "Boolean", "Score"];

export type DecisionQuestion = {
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
  showParameter = true,
}: InputProps<DecisionQuestion[], DecisionQuestionsComponentType>) {
  const { t } = useTranslation();
  if (!showParameter) return null;

  const questions = Array.isArray(value) ? value : [];
  const save = (next: DecisionQuestion[]) => handleOnNewValue({ value: next });
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
                onClick={() => save(questions.filter((_, i) => i !== index))}
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
        onClick={() => save([...questions, cloneDeep(newQuestion ?? {})])}
      >
        <IconComponent name="Plus" className="mr-1 h-4 w-4" />
        {t("decisionQuestions.add")}
      </Button>
    </div>
  );
}
