import * as Form from "@radix-ui/react-form";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "../../components/ui/button";
import BaseModal from "../../modals/baseModal";
import { LabelColorPicker } from "./LabelColorPicker";
import {
  type AnnotationLabel,
  type AnnotationProjectCreateType,
  type AnnotationProjectType,
  defaultLabelColor,
} from "./types";

type Props = {
  title: string;
  titleHeader: string;
  cancelText: string;
  confirmationText: string;
  icon?: string;
  data?: AnnotationProjectType | null;
  onConfirm: (input: AnnotationProjectCreateType) => void;
  asChild?: boolean;
  children: React.ReactNode;
};

export default function CreateProjectModal({
  title,
  titleHeader,
  cancelText,
  confirmationText,
  icon = "ImagePlus",
  data,
  onConfirm,
  asChild,
  children,
}: Props) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [labels, setLabels] = useState<AnnotationLabel[]>([]);

  useEffect(() => {
    if (open) {
      if (data) {
        setName(data.name);
        setDescription(data.description ?? "");
        setLabels(
          data.labels.map((label, index) => ({
            value: label.value,
            background: label.background ?? defaultLabelColor(index),
          })),
        );
      } else {
        setName("");
        setDescription("");
        setLabels([]);
      }
    }
  }, [open, data]);

  function handleLabelChange(index: number, patch: Partial<AnnotationLabel>) {
    setLabels((prev) =>
      prev.map((label, i) => (i === index ? { ...label, ...patch } : label)),
    );
  }

  function handleAddLabel() {
    setLabels((prev) => [
      ...prev,
      { value: "", background: defaultLabelColor(prev.length) },
    ]);
  }

  function handleRemoveLabel(index: number) {
    setLabels((prev) => prev.filter((_, i) => i !== index));
  }

  function normalizedLabels(): AnnotationLabel[] {
    const seen = new Set<string>();
    const result: AnnotationLabel[] = [];
    for (const label of labels) {
      const value = label.value.trim();
      if (!value || seen.has(value)) continue;
      seen.add(value);
      result.push({
        value,
        background: label.background ?? defaultLabelColor(result.length),
      });
    }
    return result;
  }

  const hasLabel = labels.some((label) => label.value.trim().length > 0);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const finalLabels = normalizedLabels();
    if (!name.trim() || finalLabels.length === 0) return;
    onConfirm({
      name: name.trim(),
      description: description.trim(),
      labels: finalLabels,
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
                {t("imageAnnotation.projectNameLabel")}{" "}
                <span className="font-medium text-destructive">*</span>
              </Form.Label>
              <Form.Control asChild>
                <input
                  className="primary-input mt-1"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder={t("imageAnnotation.projectNamePlaceholder")}
                />
              </Form.Control>
              <Form.Message match="valueMissing" className="field-invalid">
                {t("imageAnnotation.projectNameRequired")}
              </Form.Message>
            </Form.Field>

            <Form.Field name="description">
              <Form.Label className="data-[invalid]:label-invalid">
                {t("imageAnnotation.projectDescriptionLabel")}
              </Form.Label>
              <Form.Control asChild>
                <textarea
                  className="primary-input mt-1 min-h-[80px] resize-y"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder={t(
                    "imageAnnotation.projectDescriptionPlaceholder",
                  )}
                />
              </Form.Control>
            </Form.Field>

            <div>
              <div className="mb-1 flex items-center justify-between">
                <span className="text-sm font-medium">
                  {t("imageAnnotation.projectLabelsLabel")}{" "}
                  <span className="font-medium text-destructive">*</span>
                </span>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleAddLabel}
                >
                  <IconComponent name="Plus" className="h-3.5 w-3.5" />
                  {t("imageAnnotation.labelAdd")}
                </Button>
              </div>
              {labels.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  {t("imageAnnotation.projectLabelsRequired")}
                </p>
              ) : (
                <div className="grid gap-2">
                  {labels.map((label, index) => (
                    <div key={index} className="flex items-center gap-2">
                      <LabelColorPicker
                        color={label.background ?? defaultLabelColor(index)}
                        onChange={(color) =>
                          handleLabelChange(index, { background: color })
                        }
                      />
                      <input
                        className="primary-input min-w-0 flex-1 py-1 text-sm"
                        value={label.value}
                        onChange={(e) =>
                          handleLabelChange(index, { value: e.target.value })
                        }
                        placeholder={t("imageAnnotation.labelNamePlaceholder")}
                      />
                      <button
                        type="button"
                        onClick={() => handleRemoveLabel(index)}
                        className="shrink-0"
                        aria-label={t("imageAnnotation.labelRemove")}
                      >
                        <IconComponent
                          name="Trash2"
                          className="h-3.5 w-3.5 cursor-pointer text-destructive"
                        />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              {!hasLabel && labels.length > 0 && (
                <p className="field-invalid">
                  {t("imageAnnotation.projectLabelsRequired")}
                </p>
              )}
            </div>
          </div>

          <div className="float-right mt-5">
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
              className="mr-3"
            >
              {cancelText}
            </Button>
            <Form.Submit asChild>
              <Button disabled={!name.trim() || !hasLabel}>
                {confirmationText}
              </Button>
            </Form.Submit>
          </div>
        </Form.Root>
      </BaseModal.Content>
    </BaseModal>
  );
}
