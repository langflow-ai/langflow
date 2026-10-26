import { type DragEvent, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/utils";

interface CsvDropzoneProps {
  onFile: (file: File) => void;
  disabled?: boolean;
}

function isCsv(file: File): boolean {
  return file.name.toLowerCase().endsWith(".csv") || file.type === "text/csv";
}

export default function CsvDropzone({ onFile, disabled }: CsvDropzoneProps) {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const inputId = useId();
  const [dragging, setDragging] = useState(false);
  const [rejected, setRejected] = useState(false);

  const accept = (file: File | undefined) => {
    if (!file) return;
    if (!isCsv(file)) {
      setRejected(true);
      return;
    }
    setRejected(false);
    onFile(file);
  };

  const handleDrop = (event: DragEvent<HTMLElement>) => {
    event.preventDefault();
    setDragging(false);
    if (!disabled) accept(event.dataTransfer.files?.[0]);
  };

  return (
    <div className="flex flex-col gap-2">
      <section
        aria-label={t("evals.csv.dropTitle")}
        onDragOver={(event) => {
          event.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={cn(
          "flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed px-6 py-10 text-center transition-colors",
          dragging ? "border-primary bg-muted" : "border-border",
        )}
        data-testid="csv-dropzone"
      >
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted">
          <ForwardedIconComponent
            name="FileUp"
            aria-hidden="true"
            className="h-5 w-5 text-muted-foreground"
          />
        </div>
        <div className="flex flex-col gap-1">
          <p className="text-sm font-medium">{t("evals.csv.dropTitle")}</p>
          <p className="text-xs text-muted-foreground">
            {t("evals.csv.dropHint")}
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled}
          onClick={() => inputRef.current?.click()}
        >
          {t("evals.csv.browse")}
        </Button>
        <input
          ref={inputRef}
          id={inputId}
          type="file"
          accept=".csv,text/csv"
          className="sr-only"
          tabIndex={-1}
          aria-label={t("evals.csv.file")}
          data-testid="csv-file-input"
          onChange={(event) => {
            accept(event.target.files?.[0]);
            event.target.value = "";
          }}
        />
      </section>
      {rejected && (
        <p role="alert" className="text-xs text-destructive">
          {t("evals.csv.notCsv")}
        </p>
      )}
    </div>
  );
}
