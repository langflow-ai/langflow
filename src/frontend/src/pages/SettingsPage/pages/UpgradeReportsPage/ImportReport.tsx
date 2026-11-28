import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useImportUpgradeReport } from "@/controllers/API/queries/upgrade-reports";

const MAX_BYTES = 20 * 1024 * 1024;

export default function ImportReport({
  open,
  onOpenChange,
  onImported,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onImported: (reportId: string) => void;
}) {
  const { t } = useTranslation();
  const imported = useImportUpgradeReport();
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState(false);
  const choose = (chosen?: File | null) => {
    if (imported.isPending) return;
    imported.reset();
    setFileError(Boolean(chosen && chosen.size > MAX_BYTES));
    setFile(chosen && chosen.size <= MAX_BYTES ? chosen : null);
  };
  const close = (next: boolean) => {
    if (imported.isPending) return;
    if (!next) choose(null);
    onOpenChange(next);
  };
  const upload = () => {
    if (!file) return;
    imported.mutate(file, {
      onSuccess: (response) => {
        setFile(null);
        onOpenChange(false);
        onImported(response.id);
      },
    });
  };
  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="w-[calc(100%_-_2rem)] max-w-lg">
        <DialogHeader>
          <DialogTitle>{t("settings.upgrade.importTitle")}</DialogTitle>
          <DialogDescription>
            {t("settings.upgrade.importHelp")}
          </DialogDescription>
        </DialogHeader>
        <label
          className="flex min-h-32 cursor-pointer flex-col items-center justify-center gap-1 rounded-md border border-dashed bg-muted/40 p-4 text-center text-sm focus-within:ring-2 focus-within:ring-ring"
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            choose(event.dataTransfer.files?.[0]);
          }}
        >
          <span className="font-medium">
            {t("settings.upgrade.importDrop")}
          </span>
          <span className="text-muted-foreground">
            {t("settings.upgrade.importLimits")}
          </span>
          <input
            type="file"
            aria-label={t("settings.upgrade.file")}
            aria-describedby="upgrade-import-feedback"
            aria-invalid={fileError || imported.isError}
            accept="application/json,.json"
            className="sr-only"
            disabled={imported.isPending}
            onChange={(event) => {
              choose(event.target.files?.[0] ?? null);
              event.target.value = "";
            }}
          />
        </label>
        {file && (
          <div className="flex min-w-0 items-center gap-2 rounded-md border px-3 py-2 text-sm">
            <span className="min-w-0 flex-1 truncate">{file.name}</span>
            <Button
              variant="ghost"
              size="sm"
              disabled={imported.isPending}
              onClick={() => choose(null)}
              ignoreTitleCase
            >
              {t("settings.upgrade.importRemove")}
            </Button>
          </div>
        )}
        <div id="upgrade-import-feedback" className="text-sm">
          {(fileError || imported.isError) && (
            <p role="alert">
              {t(
                imported.error?.response?.data?.detail?.code ===
                  "unsupported_upgrade_report_format"
                  ? "settings.upgrade.unsupportedFormat"
                  : "settings.upgrade.importError",
              )}
            </p>
          )}
          {imported.isPending && (
            <p role="status">{t("settings.upgrade.importing")}</p>
          )}
        </div>
        <details className="text-sm">
          <summary className="cursor-pointer">
            {t("settings.upgrade.importHowTo")}
          </summary>
          <p className="mt-2">{t("settings.upgrade.commandHelp")}</p>
          <pre className="mt-2 whitespace-pre-wrap break-all rounded bg-muted p-3">
            <code>
              {
                "langflow upgrade-check --database-url <source-database-url> --output upgrade-report.json"
              }
            </code>
          </pre>
        </details>
        <DialogFooter>
          <Button
            variant="outline"
            disabled={imported.isPending}
            onClick={() => close(false)}
            ignoreTitleCase
          >
            {t("modal.cancelButton")}
          </Button>
          <Button
            disabled={!file || imported.isPending}
            onClick={upload}
            ignoreTitleCase
          >
            {t("settings.upgrade.import")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
