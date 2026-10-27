import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type {
  CsvImportResult,
  CsvPreview,
} from "@/controllers/API/queries/evals/types";
import {
  useImportCsv,
  usePreviewCsvImport,
} from "@/controllers/API/queries/evals/use-datasets";
import BaseModal from "@/modals/baseModal";
import useAlertStore from "@/stores/alertStore";
import { extractApiErrorMessages } from "@/utils/apiError";
import { formatFileSize } from "@/utils/stringManipulation";
import { cn } from "@/utils/utils";
import { QUIET_SELECT_TRIGGER } from "../utils/styles";
import CsvDropzone from "./CsvDropzone";

const NO_COLUMN = "__none__";

interface CsvImportDialogProps {
  datasetId: string;
  open: boolean;
  setOpen: (open: boolean) => void;
}

export default function CsvImportDialog({
  datasetId,
  open,
  setOpen,
}: CsvImportDialogProps) {
  const { t } = useTranslation();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<CsvPreview | null>(null);
  const [inputColumn, setInputColumn] = useState("");
  const [expectedColumn, setExpectedColumn] = useState(NO_COLUMN);
  const [result, setResult] = useState<CsvImportResult | null>(null);
  // A preview that answers after its file was removed or replaced, or the dialog closed, is dropped.
  const currentFile = useRef<File | null>(null);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const onError = (error: unknown) =>
    setErrorData({
      title: t("evals.csv.error"),
      list: extractApiErrorMessages(error),
    });
  const previewCsv = usePreviewCsvImport({ datasetId });
  const importCsv = useImportCsv({ datasetId }, { onError });

  const reset = () => {
    currentFile.current = null;
    setFile(null);
    setPreview(null);
    setInputColumn("");
    setExpectedColumn(NO_COLUMN);
    setResult(null);
  };

  const handleOpenChange = (next: boolean) => {
    if (!next) reset();
    setOpen(next);
  };

  const handleFile = (selected: File) => {
    currentFile.current = selected;
    setFile(selected);
    setPreview(null);
    previewCsv.mutate(
      { file: selected },
      {
        onSuccess: (data) => {
          if (currentFile.current !== selected) return;
          const headers = data.headers.filter(Boolean);
          setPreview({ ...data, headers });
          setInputColumn(headers[0] ?? "");
          setExpectedColumn(headers[1] ?? NO_COLUMN);
        },
        onError: (error) => {
          if (currentFile.current !== selected) return;
          currentFile.current = null;
          setFile(null);
          onError(error);
        },
      },
    );
  };

  const handleSubmit = () => {
    if (result) {
      handleOpenChange(false);
      return;
    }
    if (!file) return;
    importCsv.mutate(
      {
        file,
        inputColumn,
        expectedColumn: expectedColumn === NO_COLUMN ? null : expectedColumn,
      },
      { onSuccess: setResult },
    );
  };

  return (
    <BaseModal
      open={open}
      setOpen={handleOpenChange}
      size="smaller-h-full"
      onSubmit={handleSubmit}
    >
      <BaseModal.Header description={t("evals.csv.description")}>
        <ForwardedIconComponent name="FileUp" className="mr-2 h-4 w-4" />
        {t("evals.csv.title")}
      </BaseModal.Header>
      <BaseModal.Content>
        <div className="flex flex-col gap-4 px-1 pb-1">
          {result ? (
            <ImportSummary result={result} />
          ) : (
            <>
              {!file && (
                <CsvDropzone
                  onFile={handleFile}
                  disabled={previewCsv.isPending}
                />
              )}
              {file && (
                <FileCard
                  file={file}
                  rows={preview?.total_rows}
                  loading={previewCsv.isPending}
                  onRemove={reset}
                />
              )}
              {preview && (
                <>
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <ColumnSelect
                      id="csv-input-column"
                      label={t("evals.csv.inputColumn")}
                      value={inputColumn}
                      onChange={setInputColumn}
                      headers={preview.headers}
                    />
                    <ColumnSelect
                      id="csv-expected-column"
                      label={t("evals.csv.expectedColumn")}
                      value={expectedColumn}
                      onChange={setExpectedColumn}
                      headers={preview.headers}
                      noneLabel={t("evals.csv.noExpected")}
                    />
                  </div>
                  <PreviewTable
                    preview={preview}
                    inputColumn={inputColumn}
                    expectedColumn={expectedColumn}
                  />
                </>
              )}
            </>
          )}
        </div>
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{
          label: result ? t("evals.done") : t("evals.csv.import"),
          loading: importCsv.isPending,
          disabled: !result && (!preview || !inputColumn),
          dataTestId: "csv-import-submit",
        }}
      />
    </BaseModal>
  );
}

function FileCard({
  file,
  rows,
  loading,
  onRemove,
}: {
  file: File;
  rows: number | undefined;
  loading: boolean;
  onRemove: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="flex items-center gap-3 rounded-lg border px-4 py-3">
      <ForwardedIconComponent
        name={loading ? "Loader2" : "FileSpreadsheet"}
        aria-hidden="true"
        className={cn(
          "h-5 w-5 shrink-0 text-accent-emerald-foreground",
          loading && "animate-spin text-muted-foreground",
        )}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-sm font-medium" title={file.name}>
          {file.name}
        </span>
        <span className="text-xs text-muted-foreground">
          {formatFileSize(file.size)}
          {rows !== undefined &&
            ` · ${t("evals.csv.rowsFound", { count: rows })}`}
        </span>
      </div>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label={t("evals.csv.removeFile")}
        onClick={onRemove}
      >
        <ForwardedIconComponent name="X" className="h-4 w-4" />
      </Button>
    </div>
  );
}

function PreviewTable({
  preview,
  inputColumn,
  expectedColumn,
}: {
  preview: CsvPreview;
  inputColumn: string;
  expectedColumn: string;
}) {
  const { t } = useTranslation();
  const columns = [inputColumn, expectedColumn].filter(
    (column) => column && column !== NO_COLUMN,
  );
  const indexes = columns.map((column) => preview.headers.indexOf(column));
  if (preview.rows.length === 0) return null;
  return (
    <div className="flex flex-col gap-2">
      <span className="text-xs font-medium text-muted-foreground">
        {t("evals.csv.previewLabel")}
      </span>
      <div className="overflow-hidden rounded-lg border">
        <table className="w-full table-fixed text-sm">
          <thead className="bg-muted text-left text-xs text-muted-foreground">
            <tr>
              {columns.map((column, position) => (
                <th key={column} scope="col" className="px-3 py-2 font-medium">
                  {position === 0
                    ? t("evals.items.input")
                    : t("evals.items.expected")}
                  <span className="ml-1 font-normal">({column})</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {preview.rows.map((row, rowIndex) => (
              <tr key={`row-${rowIndex}`} className="border-t">
                {indexes.map((index, position) => (
                  <td
                    key={columns[position]}
                    className="truncate px-3 py-2"
                    title={row[index]}
                  >
                    {row[index] || (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ImportSummary({ result }: { result: CsvImportResult }) {
  const { t } = useTranslation();
  return (
    <div role="status" className="flex flex-col gap-4">
      <div className="flex items-center gap-3 rounded-lg border px-4 py-4">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent-emerald">
          <ForwardedIconComponent
            name="Check"
            aria-hidden="true"
            className="h-5 w-5 text-accent-emerald-foreground"
          />
        </div>
        <div className="flex flex-col">
          <span className="text-sm font-medium" data-testid="csv-import-result">
            {t("evals.csv.imported", { count: result.imported })}
          </span>
          <span className="text-xs text-muted-foreground">
            {result.skipped.length > 0
              ? t("evals.csv.skippedCount", { count: result.skipped.length })
              : t("evals.csv.noneSkipped")}
          </span>
        </div>
      </div>
      {result.skipped.length > 0 && (
        <ul className="flex max-h-40 flex-col gap-1 overflow-y-auto rounded-lg border px-4 py-3 text-xs text-muted-foreground">
          {result.skipped.map((skip) => (
            <li key={`${skip.row}-${skip.reason}`}>
              {t("evals.csv.skippedRow", {
                row: skip.row,
                reason: skip.reason,
              })}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

interface ColumnSelectProps {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  headers: string[];
  noneLabel?: string;
}

function ColumnSelect({
  id,
  label,
  value,
  onChange,
  headers,
  noneLabel,
}: ColumnSelectProps) {
  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={id}>{label}</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger id={id} className={QUIET_SELECT_TRIGGER}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {noneLabel && <SelectItem value={NO_COLUMN}>{noneLabel}</SelectItem>}
          {headers.map((header) => (
            <SelectItem key={header} value={header}>
              {header}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
