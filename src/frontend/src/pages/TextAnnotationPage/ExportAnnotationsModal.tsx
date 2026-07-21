import { useState } from "react";
import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import { exportTextAnnotationProject } from "@/controllers/API/queries/text-annotation";
import useAlertStore from "@/stores/alertStore";
import type {
  TextAnnotationExportFormat,
  TextAnnotationTaskType,
} from "@/types/text-annotation";
import { Button } from "../../components/ui/button";
import BaseModal from "../../modals/baseModal";

type Props = {
  projectId: string;
  projectName: string;
  taskType: TextAnnotationTaskType;
  children: React.ReactNode;
};

export default function ExportAnnotationsModal({
  projectId,
  projectName,
  taskType,
  children,
}: Props) {
  const { t } = useTranslation();
  const setSuccessData = useAlertStore((s) => s.setSuccessData);
  const setErrorData = useAlertStore((s) => s.setErrorData);

  const [open, setOpen] = useState(false);
  const [format, setFormat] = useState<TextAnnotationExportFormat>(
    taskType === "ner" ? "conll" : "csv",
  );
  const [isExporting, setIsExporting] = useState(false);

  const formats: {
    value: TextAnnotationExportFormat;
    label: string;
    hint: string;
  }[] = [
    {
      value: "json",
      label: t("textAnnotation.exportFormatJson"),
      hint: t("textAnnotation.exportFormatJsonHint"),
    },
    {
      value: "csv",
      label: t("textAnnotation.exportFormatCsv"),
      hint:
        taskType === "ner"
          ? t("textAnnotation.exportFormatCsvNerHint")
          : t("textAnnotation.exportFormatCsvClassificationHint"),
    },
    ...(taskType === "ner"
      ? [
          {
            value: "conll" as const,
            label: t("textAnnotation.exportFormatConll"),
            hint: t("textAnnotation.exportFormatConllHint"),
          },
        ]
      : []),
  ];

  async function handleExport() {
    setIsExporting(true);
    try {
      await exportTextAnnotationProject({
        projectId,
        format,
        fallbackName: projectName,
      });
      setSuccessData({ title: t("textAnnotation.success.exported") });
      setOpen(false);
    } catch (error) {
      setErrorData({
        title: t("textAnnotation.errors.export"),
        list: [error instanceof Error ? error.message : String(error)],
      });
    } finally {
      setIsExporting(false);
    }
  }

  return (
    <BaseModal size="small-h-full" open={open} setOpen={setOpen}>
      <BaseModal.Trigger asChild>{children}</BaseModal.Trigger>
      <BaseModal.Header description={t("textAnnotation.exportHeader")}>
        <span className="pr-2">{t("textAnnotation.exportTitle")}</span>
        <IconComponent
          name="Download"
          className="h-6 w-6 pl-1 text-foreground"
          aria-hidden="true"
        />
      </BaseModal.Header>
      <BaseModal.Content>
        <div className="grid gap-3">
          <span className="text-sm font-medium">
            {t("textAnnotation.exportFormatLabel")}
          </span>
          {formats.map((option) => (
            <label
              key={option.value}
              className={
                "flex cursor-pointer flex-col gap-1 rounded-md border p-3 " +
                (format === option.value
                  ? "border-primary bg-muted"
                  : "hover:bg-muted")
              }
            >
              <span className="flex items-center gap-2 text-sm font-medium">
                <input
                  type="radio"
                  name="export-format"
                  className="h-4 w-4"
                  checked={format === option.value}
                  onChange={() => setFormat(option.value)}
                />
                {option.label}
              </span>
              <span className="pl-6 text-xs text-muted-foreground">
                {option.hint}
              </span>
            </label>
          ))}
        </div>
        <div className="float-right mt-5">
          <Button
            variant="outline"
            onClick={() => setOpen(false)}
            className="mr-3"
          >
            {t("textAnnotation.cancelButton")}
          </Button>
          <Button
            onClick={handleExport}
            disabled={isExporting}
            loading={isExporting}
          >
            <IconComponent name="Download" className="h-4 w-4" />
            {t("textAnnotation.exportButton")}
          </Button>
        </div>
      </BaseModal.Content>
    </BaseModal>
  );
}
