import { type DragEvent, type ReactNode, useState } from "react";
import { useTranslation } from "react-i18next";
import useAlertStore from "@/stores/alertStore";
import { cn } from "@/utils/utils";
import { isCsv } from "./CsvDropzone";

/** Accepts a CSV dropped anywhere on its area; keyboard users reach the same import through a button inside. */
export default function CsvDropTarget({
  onFile,
  children,
}: {
  onFile: (file: File) => void;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const [dragging, setDragging] = useState(false);

  const acceptDrop = (event: DragEvent<HTMLElement>) => {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files?.[0];
    if (!file) return;
    if (isCsv(file)) onFile(file);
    else setErrorData({ title: t("evals.csv.notCsv") });
  };

  return (
    <section
      aria-label={t("evals.csv.dropTitle")}
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null))
          setDragging(false);
      }}
      onDrop={acceptDrop}
      className={cn(
        "flex h-full w-full rounded-lg border border-dashed transition-colors",
        dragging ? "border-primary bg-muted/40" : "border-transparent",
      )}
      data-testid="csv-drop-target"
    >
      {children}
    </section>
  );
}
