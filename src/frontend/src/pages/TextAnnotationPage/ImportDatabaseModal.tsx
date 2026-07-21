import * as Form from "@radix-ui/react-form";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import {
  usePostTextAnnotationImportDatabase,
  usePreviewTextAnnotationDatabaseImport,
} from "@/controllers/API/queries/text-annotation";
import useAlertStore from "@/stores/alertStore";
import type { DatabaseImportPreviewResponseType } from "@/types/text-annotation";
import { Button } from "../../components/ui/button";
import BaseModal from "../../modals/baseModal";

type Props = {
  projectId: string;
  children: React.ReactNode;
};

export default function ImportDatabaseModal({ projectId, children }: Props) {
  const { t } = useTranslation();
  const setSuccessData = useAlertStore((s) => s.setSuccessData);
  const setErrorData = useAlertStore((s) => s.setErrorData);

  const [open, setOpen] = useState(false);
  const [connectionUri, setConnectionUri] = useState("");
  const [tableName, setTableName] = useState("");
  const [textColumn, setTextColumn] = useState("");
  const [nameColumn, setNameColumn] = useState("");
  const [limit, setLimit] = useState(1000);
  const [preview, setPreview] =
    useState<DatabaseImportPreviewResponseType | null>(null);

  const { mutate: previewConnection, isPending: isPreviewing } =
    usePreviewTextAnnotationDatabaseImport({});
  const { mutate: importDatabase, isPending: isImporting } =
    usePostTextAnnotationImportDatabase({});

  useEffect(() => {
    if (open) {
      setConnectionUri("");
      setTableName("");
      setTextColumn("");
      setNameColumn("");
      setLimit(1000);
      setPreview(null);
    }
  }, [open]);

  const canPreview =
    connectionUri.trim().length > 0 && tableName.trim().length > 0;
  const canImport = canPreview && textColumn.trim().length > 0;

  function handlePreview() {
    if (!canPreview) return;
    previewConnection(
      {
        projectId,
        connection_uri: connectionUri.trim(),
        table_name: tableName.trim(),
        sample_size: 5,
      },
      {
        onSuccess: (data) => {
          setPreview(data);
          if (!textColumn && data.columns.length > 0) {
            setTextColumn(data.columns[0]);
          }
        },
        onError: (error) => {
          setPreview(null);
          setErrorData({
            title: t("textAnnotation.errors.importDatabase"),
            list: [error.message],
          });
        },
      },
    );
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canImport) return;
    importDatabase(
      {
        projectId,
        connection_uri: connectionUri.trim(),
        table_name: tableName.trim(),
        text_column: textColumn.trim(),
        name_column: nameColumn.trim() || undefined,
        limit,
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
            title: t("textAnnotation.errors.importDatabase"),
            list: [error.message],
          }),
      },
    );
  }

  return (
    <BaseModal size="large-h-full" open={open} setOpen={setOpen}>
      <BaseModal.Trigger asChild>{children}</BaseModal.Trigger>
      <BaseModal.Header description={t("textAnnotation.importDbHeader")}>
        <span className="pr-2">{t("textAnnotation.importDbTitle")}</span>
        <IconComponent
          name="Database"
          className="h-6 w-6 pl-1 text-foreground"
          aria-hidden="true"
        />
      </BaseModal.Header>
      <BaseModal.Content>
        <Form.Root onSubmit={handleSubmit}>
          <div className="grid gap-5">
            <Form.Field name="connectionUri">
              <Form.Label className="data-[invalid]:label-invalid">
                {t("textAnnotation.dbConnectionUriLabel")}{" "}
                <span className="font-medium text-destructive">*</span>
              </Form.Label>
              <Form.Control asChild>
                <input
                  className="primary-input mt-1"
                  required
                  value={connectionUri}
                  onChange={(e) => setConnectionUri(e.target.value)}
                  placeholder={t("textAnnotation.dbConnectionUriPlaceholder")}
                />
              </Form.Control>
            </Form.Field>

            <div className="grid grid-cols-2 gap-4">
              <Form.Field name="tableName">
                <Form.Label className="data-[invalid]:label-invalid">
                  {t("textAnnotation.dbTableLabel")}{" "}
                  <span className="font-medium text-destructive">*</span>
                </Form.Label>
                <Form.Control asChild>
                  <input
                    className="primary-input mt-1"
                    required
                    value={tableName}
                    onChange={(e) => setTableName(e.target.value)}
                    placeholder={t("textAnnotation.dbTablePlaceholder")}
                  />
                </Form.Control>
              </Form.Field>

              <Form.Field name="limit">
                <Form.Label>{t("textAnnotation.dbLimitLabel")}</Form.Label>
                <Form.Control asChild>
                  <input
                    className="primary-input mt-1"
                    type="number"
                    min={1}
                    max={10000}
                    value={limit}
                    onChange={(e) => setLimit(Number(e.target.value) || 1000)}
                  />
                </Form.Control>
              </Form.Field>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Form.Field name="textColumn">
                <Form.Label className="data-[invalid]:label-invalid">
                  {t("textAnnotation.dbTextColumnLabel")}{" "}
                  <span className="font-medium text-destructive">*</span>
                </Form.Label>
                {preview && preview.columns.length > 0 ? (
                  <select
                    className="primary-input mt-1"
                    value={textColumn}
                    onChange={(e) => setTextColumn(e.target.value)}
                  >
                    {preview.columns.map((column) => (
                      <option key={column} value={column}>
                        {column}
                      </option>
                    ))}
                  </select>
                ) : (
                  <Form.Control asChild>
                    <input
                      className="primary-input mt-1"
                      required
                      value={textColumn}
                      onChange={(e) => setTextColumn(e.target.value)}
                      placeholder={t("textAnnotation.dbTextColumnPlaceholder")}
                    />
                  </Form.Control>
                )}
              </Form.Field>

              <Form.Field name="nameColumn">
                <Form.Label>{t("textAnnotation.dbNameColumnLabel")}</Form.Label>
                {preview && preview.columns.length > 0 ? (
                  <select
                    className="primary-input mt-1"
                    value={nameColumn}
                    onChange={(e) => setNameColumn(e.target.value)}
                  >
                    <option value="">-</option>
                    {preview.columns.map((column) => (
                      <option key={column} value={column}>
                        {column}
                      </option>
                    ))}
                  </select>
                ) : (
                  <Form.Control asChild>
                    <input
                      className="primary-input mt-1"
                      value={nameColumn}
                      onChange={(e) => setNameColumn(e.target.value)}
                      placeholder={t("textAnnotation.dbNameColumnPlaceholder")}
                    />
                  </Form.Control>
                )}
              </Form.Field>
            </div>

            <div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handlePreview}
                disabled={!canPreview || isPreviewing}
                loading={isPreviewing}
              >
                <IconComponent name="PlugZap" className="h-4 w-4" />
                {t("textAnnotation.dbPreviewButton")}
              </Button>
            </div>

            {preview && (
              <div className="max-h-56 overflow-auto rounded-md border custom-scroll">
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-muted">
                    <tr>
                      {preview.columns.map((column) => (
                        <th
                          key={column}
                          className={
                            "px-2 py-1 text-left font-medium " +
                            (column === textColumn ? "text-primary" : "")
                          }
                        >
                          {column}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.rows.map((row, rowIndex) => (
                      <tr key={rowIndex} className="border-t">
                        {preview.columns.map((column) => (
                          <td
                            key={column}
                            className="max-w-64 truncate px-2 py-1 text-muted-foreground"
                          >
                            {String(row[column] ?? "")}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
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
              <Button
                disabled={!canImport || isImporting}
                loading={isImporting}
              >
                {t("textAnnotation.importButton")}
              </Button>
            </Form.Submit>
          </div>
        </Form.Root>
      </BaseModal.Content>
    </BaseModal>
  );
}
