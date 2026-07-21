import * as Form from "@radix-ui/react-form";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import { usePostTextAnnotationImportCsv } from "@/controllers/API/queries/text-annotation";
import useAlertStore from "@/stores/alertStore";
import { Button } from "../../components/ui/button";
import BaseModal from "../../modals/baseModal";

type Props = {
  projectId: string;
  children: React.ReactNode;
};

export default function ImportCsvModal({ projectId, children }: Props) {
  const { t } = useTranslation();
  const setSuccessData = useAlertStore((s) => s.setSuccessData);
  const setErrorData = useAlertStore((s) => s.setErrorData);

  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [textColumn, setTextColumn] = useState("");
  const [nameColumn, setNameColumn] = useState("");
  const [hasHeader, setHasHeader] = useState(true);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const { mutate: importCsv, isPending } = usePostTextAnnotationImportCsv({});

  useEffect(() => {
    if (open) {
      setFile(null);
      setTextColumn("");
      setNameColumn("");
      setHasHeader(true);
    }
  }, [open]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    importCsv(
      {
        projectId,
        file,
        textColumn: textColumn.trim() || undefined,
        nameColumn: nameColumn.trim() || undefined,
        hasHeader,
      },
      {
        onSuccess: (data) => {
          setSuccessData({
            title: t("textAnnotation.success.imported", {
              created: data.created,
              skipped: data.skipped,
            }),
          });
          setOpen(false);
        },
        onError: (error) =>
          setErrorData({
            title: t("textAnnotation.errors.importCsv"),
            list: [error.message],
          }),
      },
    );
  }

  return (
    <BaseModal size="medium-h-full" open={open} setOpen={setOpen}>
      <BaseModal.Trigger asChild>{children}</BaseModal.Trigger>
      <BaseModal.Header description={t("textAnnotation.importCsvHeader")}>
        <span className="pr-2">{t("textAnnotation.importCsvTitle")}</span>
        <IconComponent
          name="FileSpreadsheet"
          className="h-6 w-6 pl-1 text-foreground"
          aria-hidden="true"
        />
      </BaseModal.Header>
      <BaseModal.Content>
        <Form.Root onSubmit={handleSubmit}>
          <div className="grid gap-5">
            <Form.Field name="file">
              <Form.Label className="data-[invalid]:label-invalid">
                {t("textAnnotation.importCsvFileLabel")}{" "}
                <span className="font-medium text-destructive">*</span>
              </Form.Label>
              <div
                className="mt-1 flex cursor-pointer items-center justify-center gap-2 rounded-md border border-dashed px-3 py-6 text-sm text-muted-foreground hover:bg-muted"
                onClick={() => fileInputRef.current?.click()}
              >
                <IconComponent name="Upload" className="h-4 w-4" />
                {file ? file.name : t("textAnnotation.importCsvFileHint")}
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,text/csv"
                className="hidden"
                onChange={(e) => {
                  setFile(e.target.files?.[0] ?? null);
                  e.target.value = "";
                }}
              />
              {!file && (
                <p className="field-invalid">
                  {t("textAnnotation.importCsvFileRequired")}
                </p>
              )}
            </Form.Field>

            <Form.Field name="textColumn">
              <Form.Label>
                {t("textAnnotation.importCsvTextColumnLabel")}
              </Form.Label>
              <Form.Control asChild>
                <input
                  className="primary-input mt-1"
                  value={textColumn}
                  onChange={(e) => setTextColumn(e.target.value)}
                  placeholder={t(
                    "textAnnotation.importCsvTextColumnPlaceholder",
                  )}
                />
              </Form.Control>
            </Form.Field>

            <Form.Field name="nameColumn">
              <Form.Label>
                {t("textAnnotation.importCsvNameColumnLabel")}
              </Form.Label>
              <Form.Control asChild>
                <input
                  className="primary-input mt-1"
                  value={nameColumn}
                  onChange={(e) => setNameColumn(e.target.value)}
                  placeholder={t(
                    "textAnnotation.importCsvNameColumnPlaceholder",
                  )}
                />
              </Form.Control>
            </Form.Field>

            <label className="flex cursor-pointer items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="h-4 w-4"
                checked={hasHeader}
                onChange={(e) => setHasHeader(e.target.checked)}
              />
              {t("textAnnotation.importCsvHasHeaderLabel")}
            </label>
          </div>

          <div className="float-right mt-5">
            <Button
              variant="outline"
              onClick={() => setOpen(false)}
              className="mr-3"
              type="button"
            >
              {t("textAnnotation.cancelButton")}
            </Button>
            <Form.Submit asChild>
              <Button disabled={!file || isPending} loading={isPending}>
                {t("textAnnotation.importButton")}
              </Button>
            </Form.Submit>
          </div>
        </Form.Root>
      </BaseModal.Content>
    </BaseModal>
  );
}
