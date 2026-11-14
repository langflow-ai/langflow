import { api } from "@/controllers/API/api";
import { parseContentDispositionFilename } from "@/utils/parse-content-disposition-filename";

export async function downloadCsv(url: string, fallbackName: string) {
  const response = await api.get<Blob>(url, { responseType: "blob" });
  const header = response.headers?.["content-disposition"];
  const filename = parseContentDispositionFilename(
    typeof header === "string" ? header : null,
    fallbackName,
  );
  const objectUrl = window.URL.createObjectURL(
    new Blob([response.data], { type: "text/csv" }),
  );
  const link = document.createElement("a");
  link.href = objectUrl;
  link.setAttribute("download", filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(objectUrl);
}
