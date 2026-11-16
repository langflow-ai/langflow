import { useRef } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import useAlertStore from "@/stores/alertStore";
import { isCsv } from "./CsvDropzone";

interface ImportCsvButtonProps {
  onFile: (file: File) => void;
  loading?: boolean;
  testId: string;
}

/** Opens the file picker straight away; the column mapping comes after a file is chosen. */
export default function ImportCsvButton({
  onFile,
  loading = false,
  testId,
}: ImportCsvButtonProps) {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  return (
    <>
      <Button
        variant="outline"
        className="flex items-center gap-2 font-semibold"
        loading={loading}
        onClick={() => inputRef.current?.click()}
        data-testid={testId}
      >
        <ForwardedIconComponent name="FileUp" className="h-4 w-4" />
        {t("evals.csv.title")}
      </Button>
      <input
        ref={inputRef}
        type="file"
        accept=".csv,text/csv"
        className="sr-only"
        tabIndex={-1}
        aria-label={t("evals.csv.file")}
        data-testid={`${testId}-input`}
        onChange={(event) => {
          const file = event.target.files?.[0];
          event.target.value = "";
          if (!file) return;
          if (isCsv(file)) onFile(file);
          else setErrorData({ title: t("evals.csv.notCsv") });
        }}
      />
    </>
  );
}
