import type { TextAnnotationExportFormat } from "@/types/text-annotation";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { extractApiErrorMessage } from "../../helpers/extract-api-error-message";

/**
 * Download an exported annotation project (BERT training formats) as a file.
 * Not a hook — the export endpoint streams a file attachment.
 */
export async function exportTextAnnotationProject({
  projectId,
  format,
  fallbackName,
}: {
  projectId: string;
  format: TextAnnotationExportFormat;
  fallbackName: string;
}): Promise<void> {
  let response: { data: Blob; headers: Record<string, string> };
  try {
    response = await api.get(
      `${getURL("TEXT_ANNOTATION_PROJECTS")}/${projectId}/export`,
      { params: { format }, responseType: "blob" },
    );
  } catch (error: unknown) {
    throw new Error(
      extractApiErrorMessage(
        error as Parameters<typeof extractApiErrorMessage>[0],
        "Failed to export annotations",
      ),
    );
  }

  const disposition: string = response.headers["content-disposition"] ?? "";
  const match = /filename\*?=(?:UTF-8''|")?([^";]+)/i.exec(disposition);
  const filename = match
    ? decodeURIComponent(match[1].replace(/"/g, ""))
    : `${fallbackName}-${format}.txt`;

  const url = window.URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
