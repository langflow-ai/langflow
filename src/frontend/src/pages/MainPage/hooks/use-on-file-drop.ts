import { useCallback, useEffect, useRef } from "react";
import useUploadFlow from "@/hooks/flows/use-upload-flow";
import { CONSOLE_ERROR_MSG } from "../../../constants/alerts_constants";
import useAlertStore from "../../../stores/alertStore";

function isEditablePasteTarget(target: EventTarget | null): boolean {
  // Do not hijack paste when the user is typing in an input/editor.
  if (!target || !(target instanceof HTMLElement)) return false;
  return (
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target.isContentEditable === true
  );
}

function stripJsonCodeFence(text: string): string {
  // Accept common "```json ... ```" clipboard formats.
  const trimmed = text.trim();
  return trimmed
    .replace(/^```(?:json)?\s*/i, "")
    .replace(/\s*```$/i, "")
    .trim();
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function looksLikeFlowImportPayload(payload: unknown): boolean {
  if (!isRecord(payload)) return false;

  // Collection export: { flows: FlowType[] }
  if (Array.isArray(payload.flows)) {
    return true;
  }

  // Single flow export: FlowType shape (at least { data: { nodes: [], edges: [] } })
  if (!isRecord(payload.data)) return false;
  return Array.isArray(payload.data.nodes) && Array.isArray(payload.data.edges);
}

const useFileDrop = (type?: string) => {
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const uploadFlow = useUploadFlow();

  const lastUploadTime = useRef<number>(0);
  const DEBOUNCE_INTERVAL = 1000;

  const uploadFiles = useCallback(
    (files: File[]) => {
      const currentTime = Date.now();
      if (currentTime - lastUploadTime.current < DEBOUNCE_INTERVAL) return;
      lastUploadTime.current = currentTime;

      uploadFlow({
        files,
        isComponent:
          type === "components" ? true : type === "flows" ? false : undefined,
      })
        .then(() => {
          setSuccessData({
            title: "All files uploaded successfully",
          });
        })
        .catch((error) => {
          console.error(error);
          setErrorData({
            title: CONSOLE_ERROR_MSG,
            list: [(error as Error).message],
          });
        });
    },
    [type, uploadFlow, setSuccessData, setErrorData],
  );

  const handleFileDrop = useCallback(
    (e) => {
      e.preventDefault();

      if (e.dataTransfer?.types?.every((type) => type === "Files")) {
        const files: File[] = Array.from(e.dataTransfer.files);
        uploadFiles(files);
      }
    },
    [uploadFiles],
  );

  useEffect(() => {
    const handlePaste = (event: ClipboardEvent) => {
      // Keep paste import disabled when the UI is not accepting flow drops (e.g. MCP tab).
      if (type === "mcp") return;
      if (isEditablePasteTarget(event.target)) return;

      const rawText =
        event.clipboardData?.getData("text/plain") ??
        event.clipboardData?.getData("text") ??
        "";
      if (!rawText) return;

      const maybeJson = stripJsonCodeFence(rawText);
      if (!maybeJson) return;

      let parsed: unknown;
      try {
        parsed = JSON.parse(maybeJson);
      } catch {
        return;
      }

      if (!looksLikeFlowImportPayload(parsed)) return;

      // At this point we are confident this is a flow JSON, so we can hijack paste.
      event.preventDefault();
      event.stopPropagation();

      const safeTimestamp = new Date().toISOString().replace(/[:.]/g, "-");
      const file = new File(
        [JSON.stringify(parsed)],
        `pasted-flow-${safeTimestamp}.json`,
        { type: "application/json" },
      );
      uploadFiles([file]);
    };

    // Use capture to run before most other handlers, but only prevent default when importing.
    document.addEventListener("paste", handlePaste, true);
    return () => {
      document.removeEventListener("paste", handlePaste, true);
    };
  }, [uploadFiles]);

  return handleFileDrop;
};

export default useFileDrop;
