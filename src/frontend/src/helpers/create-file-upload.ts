import { DEFAULT_FILE_PICKER_TIMEOUT } from "@/constants/constants";

export function createFileUpload(props?: {
  accept?: string;
  multiple?: boolean;
}): Promise<File[]> {
  return new Promise((resolve) => {
    // Create input element
    const input = document.createElement("input");
    input.type = "file";
    input.style.position = "fixed";
    input.style.top = "0";
    input.style.left = "0";
    input.style.opacity = "0.001";
    input.style.pointerEvents = "none";
    input.accept = props?.accept ?? ".json";
    input.multiple = props?.multiple ?? true;

    let isHandled = false;

    const cleanup = () => {
      if (document.body.contains(input)) {
        try {
          document.body.removeChild(input);
        } catch (error) {
          console.warn("Error removing input element:", error);
        }
      }
      input.removeEventListener("change", handleChange);
      document.removeEventListener("focus", handleFocus);
    };

    const handleChange = (event: Event) => {
      if (isHandled) return;
      isHandled = true;

      const files = Array.from((event.target as HTMLInputElement).files || []);
      cleanup();
      resolve(files);
    };

    const handleFocus = () => {
      setTimeout(() => {
        if (!isHandled) {
          isHandled = true;
          cleanup();
          resolve([]);
        }
      }, 100);
    };

    input.addEventListener("change", handleChange);
    document.addEventListener("focus", handleFocus);

    document.body.appendChild(input);

    requestAnimationFrame(() => {
      if (!isHandled) {
        input.click();
      }
    });

    setTimeout(() => {
      if (!isHandled) {
        isHandled = true;
        cleanup();
        resolve([]);
      }
    }, DEFAULT_FILE_PICKER_TIMEOUT);
  });
}
