import * as Form from "@radix-ui/react-form";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import type {
  TextAnnotationLabel,
  TextAnnotationProjectCreateType,
  TextAnnotationProjectType,
  TextAnnotationTaskType,
} from "@/types/text-annotation";
import { Button } from "../../components/ui/button";
import BaseModal from "../../modals/baseModal";

type Props = {
  title: string;
  titleHeader: string;
  cancelText: string;
  confirmationText: string;
  icon?: string;
  data?: TextAnnotationProjectType | null;
  onConfirm: (input: TextAnnotationProjectCreateType) => void;
  asChild?: boolean;
  children: React.ReactNode;
};

export default function CreateProjectModal({
  title,
  titleHeader,
  cancelText,
  confirmationText,
  icon = "FileText",
  data,
  onConfirm,
  asChild,
  children,
}: Props) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [entityLabelsText, setEntityLabelsText] = useState("");
  const [categoryLabelsText, setCategoryLabelsText] = useState("");
  const [taskType, setTaskType] = useState<TextAnnotationTaskType>("ner");

  useEffect(() => {
    if (open) {
      if (data) {
        setName(data.name);
        setDescription(data.description ?? "");
        setEntityLabelsText(
          data.entity_labels.map((label) => label.value).join(", "),
        );
        setCategoryLabelsText(
          data.category_labels.map((label) => label.value).join(", "),
        );
        setTaskType(data.task_type ?? "ner");
      } else {
        setName("");
        setDescription("");
        setEntityLabelsText("");
        setCategoryLabelsText("");
        setTaskType("ner");
      }
    }
  }, [open, data]);

  function parseLabels(
    text: string,
    existing: TextAnnotationLabel[] | undefined,
  ): TextAnnotationLabel[] {
    const backgrounds = new Map(
      (existing ?? []).map((label) => [label.value, label.background ?? null]),
    );
    const seen = new Set<string>();
    return text
      .split(",")
      .map((s) => s.trim())
      .filter((s) => s.length > 0)
      .filter((s) => {
        if (seen.has(s)) return false;
        seen.add(s);
        return true;
      })
      .map((value) => ({ value, background: backgrounds.get(value) ?? null }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const isNer = taskType === "ner";
    onConfirm({
      name: name.trim(),
      description: description.trim(),
      task_type: taskType,
      entity_labels: isNer
        ? parseLabels(entityLabelsText, data?.entity_labels)
        : (data?.entity_labels ?? []),
      category_labels: !isNer
        ? parseLabels(categoryLabelsText, data?.category_labels)
        : (data?.category_labels ?? []),
    });
    setOpen(false);
  }

  return (
    <BaseModal size="medium-h-full" open={open} setOpen={setOpen}>
      <BaseModal.Trigger asChild={asChild}>{children}</BaseModal.Trigger>
      <BaseModal.Header description={titleHeader}>
        <span className="pr-2">{title}</span>
        <IconComponent
          name={icon}
          className="h-6 w-6 pl-1 text-foreground"
          aria-hidden="true"
        />
      </BaseModal.Header>
      <BaseModal.Content>
        <Form.Root onSubmit={handleSubmit}>
          <div className="grid gap-5">
            <Form.Field name="name">
              <Form.Label className="data-[invalid]:label-invalid">
                {t("textAnnotation.projectNameLabel")}{" "}
                <span className="font-medium text-destructive">*</span>
              </Form.Label>
              <Form.Control asChild>
                <input
                  className="primary-input mt-1"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder={t("textAnnotation.projectNamePlaceholder")}
                />
              </Form.Control>
              <Form.Message match="valueMissing" className="field-invalid">
                {t("textAnnotation.projectNameRequired")}
              </Form.Message>
            </Form.Field>

            <Form.Field name="description">
              <Form.Label className="data-[invalid]:label-invalid">
                {t("textAnnotation.projectDescriptionLabel")}
              </Form.Label>
              <Form.Control asChild>
                <textarea
                  className="primary-input mt-1 min-h-[80px] resize-y"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder={t(
                    "textAnnotation.projectDescriptionPlaceholder",
                  )}
                />
              </Form.Control>
            </Form.Field>

            <Form.Field name="taskType">
              <Form.Label className="data-[invalid]:label-invalid">
                {t("textAnnotation.projectTaskTypeLabel")}
              </Form.Label>
              <div className="mt-1 flex gap-4">
                <label className="flex cursor-pointer items-center gap-2">
                  <input
                    type="radio"
                    name="taskType"
                    className="h-4 w-4"
                    checked={taskType === "ner"}
                    onChange={() => setTaskType("ner")}
                  />
                  <span className="text-sm">
                    {t("textAnnotation.projectTaskTypeNer")}
                  </span>
                </label>
                <label className="flex cursor-pointer items-center gap-2">
                  <input
                    type="radio"
                    name="taskType"
                    className="h-4 w-4"
                    checked={taskType === "classification"}
                    onChange={() => setTaskType("classification")}
                  />
                  <span className="text-sm">
                    {t("textAnnotation.projectTaskTypeClassification")}
                  </span>
                </label>
              </div>
            </Form.Field>

            {taskType === "ner" && (
              <Form.Field name="entityLabels">
                <Form.Label className="data-[invalid]:label-invalid">
                  {t("textAnnotation.projectEntityLabelsLabel")}{" "}
                  <span className="font-medium text-destructive">*</span>
                </Form.Label>
                <Form.Control asChild>
                  <input
                    className="primary-input mt-1"
                    required={entityLabelsText.trim().length === 0}
                    value={entityLabelsText}
                    onChange={(e) => setEntityLabelsText(e.target.value)}
                    placeholder={t(
                      "textAnnotation.projectEntityLabelsPlaceholder",
                    )}
                  />
                </Form.Control>
                {entityLabelsText.trim().length === 0 && (
                  <p className="field-invalid">
                    {t("textAnnotation.projectEntityLabelsRequired")}
                  </p>
                )}
              </Form.Field>
            )}

            {taskType === "classification" && (
              <Form.Field name="categoryLabels">
                <Form.Label className="data-[invalid]:label-invalid">
                  {t("textAnnotation.projectCategoryLabelsLabel")}{" "}
                  <span className="font-medium text-destructive">*</span>
                </Form.Label>
                <Form.Control asChild>
                  <input
                    className="primary-input mt-1"
                    required={categoryLabelsText.trim().length === 0}
                    value={categoryLabelsText}
                    onChange={(e) => setCategoryLabelsText(e.target.value)}
                    placeholder={t(
                      "textAnnotation.projectCategoryLabelsPlaceholder",
                    )}
                  />
                </Form.Control>
                {categoryLabelsText.trim().length === 0 && (
                  <p className="field-invalid">
                    {t("textAnnotation.projectCategoryLabelsRequired")}
                  </p>
                )}
              </Form.Field>
            )}
          </div>

          <div className="float-right mt-5">
            <Button
              variant="outline"
              onClick={() => setOpen(false)}
              className="mr-3"
            >
              {cancelText}
            </Button>
            <Form.Submit asChild>
              <Button>{confirmationText}</Button>
            </Form.Submit>
          </div>
        </Form.Root>
      </BaseModal.Content>
    </BaseModal>
  );
}
