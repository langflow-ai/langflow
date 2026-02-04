import { useState } from "react";
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
import { useImportCsv } from "@/controllers/API/queries/datasets/use-import-csv";
import { usePreviewCsv } from "@/controllers/API/queries/datasets/use-preview-csv";
import { createFileUpload } from "@/helpers/create-file-upload";
import useAlertStore from "@/stores/alertStore";
import BaseModal from "../baseModal";

interface ImportCsvModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  datasetId: string;
  onSuccess?: () => void;
}

export default function ImportCsvModal({
  open,
  setOpen,
  datasetId,
  onSuccess,
}: ImportCsvModalProps): JSX.Element {
  const [file, setFile] = useState<File | null>(null);
  const [columns, setColumns] = useState<string[]>([]);
  const [preview, setPreview] = useState<Record<string, string>[]>([]);
  const [inputColumn, setInputColumn] = useState<string>("");
  const [expectedOutputColumn, setExpectedOutputColumn] = useState<string>("");

  const { setErrorData, setSuccessData } = useAlertStore((state) => ({
    setErrorData: state.setErrorData,
    setSuccessData: state.setSuccessData,
  }));

  const previewCsvMutation = usePreviewCsv({
    onSuccess: (data) => {
      setColumns(data.columns);
      setPreview(data.preview);
      // Auto-select columns if they match common names
      if (data.columns.includes("input")) {
        setInputColumn("input");
      } else if (data.columns.length > 0) {
        setInputColumn(data.columns[0]);
      }
      if (data.columns.includes("expected_output")) {
        setExpectedOutputColumn("expected_output");
      } else if (data.columns.includes("output")) {
        setExpectedOutputColumn("output");
      } else if (data.columns.length > 1) {
        setExpectedOutputColumn(data.columns[1]);
      }
    },
    onError: (error: any) => {
      setErrorData({
        title: "Failed to parse CSV file",
        list: [error?.message || "Unable to read the file"],
      });
    },
  });

  const importCsvMutation = useImportCsv({
    onSuccess: (data) => {
      setSuccessData({ title: `Successfully imported ${data.imported} items` });
      handleClose();
      onSuccess?.();
    },
    onError: (error: any) => {
      setErrorData({
        title: "Failed to import CSV",
        list: [
          error?.response?.data?.detail ||
            error?.message ||
            "An unknown error occurred",
        ],
      });
    },
  });

  const handleSelectFile = async () => {
    const files = await createFileUpload({
      accept: ".csv",
      multiple: false,
    });

    if (files.length > 0) {
      const selectedFile = files[0];
      setFile(selectedFile);
      previewCsvMutation.mutate({ file: selectedFile });
    }
  };

  const handleSubmit = () => {
    if (!file || !inputColumn || !expectedOutputColumn) {
      setErrorData({
        title: "Validation error",
        list: ["Please select a file and map both columns"],
      });
      return;
    }

    importCsvMutation.mutate({
      datasetId,
      file,
      inputColumn,
      expectedOutputColumn,
    });
  };

  const handleClose = () => {
    setOpen(false);
    setFile(null);
    setColumns([]);
    setPreview([]);
    setInputColumn("");
    setExpectedOutputColumn("");
  };

  if (!open) return <></>;

  return (
    <BaseModal open={open} setOpen={handleClose} size="medium-h-full">
      <BaseModal.Header description="Upload a CSV file and map columns to input/expected output fields.">
        Import CSV
      </BaseModal.Header>
      <BaseModal.Content className="flex flex-col gap-6 p-4">
        {/* File Upload */}
        <div
          onClick={handleSelectFile}
          className="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-muted-foreground/25 p-4 transition-colors hover:border-primary/50"
        >
          <ForwardedIconComponent
            name="Upload"
            className="mb-2 h-6 w-6 text-muted-foreground"
          />
          {file ? (
            <div className="text-center">
              <p className="font-medium">{file.name}</p>
              <p className="text-sm text-muted-foreground">
                Click to replace
              </p>
            </div>
          ) : (
            <div className="text-center">
              <p className="font-medium">Click to select CSV file</p>
              <p className="text-sm text-muted-foreground">
                or drag and drop
              </p>
            </div>
          )}
        </div>

        {/* Column Mapping */}
        {columns.length > 0 && (
          <div className="flex flex-col gap-4">
            <h3 className="font-medium">Column Mapping</h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="flex flex-col gap-2">
                <Label>Input Column</Label>
                <Select value={inputColumn} onValueChange={setInputColumn}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select column" />
                  </SelectTrigger>
                  <SelectContent>
                    {columns.map((col) => (
                      <SelectItem key={col} value={col}>
                        {col}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-2">
                <Label>Expected Output Column</Label>
                <Select
                  value={expectedOutputColumn}
                  onValueChange={setExpectedOutputColumn}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select column" />
                  </SelectTrigger>
                  <SelectContent>
                    {columns.map((col) => (
                      <SelectItem key={col} value={col}>
                        {col}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
        )}

        {/* Preview */}
        {preview.length > 0 && inputColumn && expectedOutputColumn && (
          <div className="flex flex-col gap-2">
            <h3 className="font-medium">Preview (first 5 rows)</h3>
            <div className="overflow-auto rounded-md border">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-muted">
                  <tr>
                    <th className="p-2 text-left font-medium">Input</th>
                    <th className="p-2 text-left font-medium">
                      Expected Output
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {preview.map((row, idx) => (
                    <tr key={idx} className="border-t">
                      <td className="max-w-xs truncate p-2">
                        {row[inputColumn]}
                      </td>
                      <td className="max-w-xs truncate p-2">
                        {row[expectedOutputColumn]}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{
          label: "Import",
          loading: importCsvMutation.isPending,
          disabled:
            !file ||
            !inputColumn ||
            !expectedOutputColumn ||
            importCsvMutation.isPending,
          dataTestId: "btn-import-csv",
          onClick: handleSubmit,
        }}
      />
    </BaseModal>
  );
}
