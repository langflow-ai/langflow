import {
  BACKEND_URL,
  BASE_URL_API,
} from "../../../../../../constants/constants";

let isDownloading = false;

export default async function handleDownload({
  fileName,
  content,
}: {
  fileName: string;
  content: string;
}): Promise<void> {
  if (isDownloading) return;

  try {
    isDownloading = true;

    const response = await fetch(`${BASE_URL_API}files/download/${content}`);
    if (!response.ok) {
      throw new Error("Network response was not ok");
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);

    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", fileName); // Set the filename
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    URL.revokeObjectURL(url); // Clean up the URL object
  } catch (error) {
    console.error("Failed to download file:", error);
  } finally {
    isDownloading = false;
  }
}
