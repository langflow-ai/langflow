import { FlowType } from "@/types/flow";

export async function customDownloadNodeJson(NodeFLow: FlowType) {
  // Fallback to browser download for web version
  const element = document.createElement("a");
  const file = new Blob([JSON.stringify(NodeFLow)], {
    type: "application/json",
  });
  element.href = URL.createObjectURL(file);
  element.download = `${NodeFLow?.name ?? "node"}.json`;
  element.click();
}
