import {
  BACKEND_URL,
  BASE_URL_API,
} from "../../../../../../constants/constants";

export default async function handleDownload({
  fileName,
  content,
}: {
  fileName: string;
  content: string;
}): Promise<void> {
  try {
    const response = await fetch(
      `${BACKEND_URL.slice(0, BACKEND_URL.length - 1)}${BASE_URL_API}files/download/${content}`,
    );
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
  }
}
