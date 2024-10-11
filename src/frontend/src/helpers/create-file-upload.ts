export function createFileUpload(props?: {
  accept?: string;
  multiple?: boolean;
}): Promise<File[]> {
  return new Promise((resolve) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = props?.accept ?? ".json";
    input.multiple = props?.multiple ?? true;
    input.style.display = "none";

    let isResolved = false;

    const cleanup = () => {
      if (input && input.parentNode) {
        input.parentNode.removeChild(input);
      }
      window.removeEventListener("focus", handleFocus);
    };

    const handleChange = (e: Event) => {
      if (!isResolved) {
        isResolved = true;
        const files = Array.from((e.target as HTMLInputElement).files!);
        cleanup();
        resolve(files);
      }
    };

    const handleFocus = () => {
      setTimeout(() => {
        if (!isResolved) {
          isResolved = true;
          cleanup();
          resolve([]);
        }
      }, 300);
    };

    input.addEventListener("change", handleChange);
    window.addEventListener("focus", handleFocus);

    document.body.appendChild(input);
    input.click();

    setTimeout(() => {
      if (!isResolved) {
        isResolved = true;
        cleanup();
        resolve([]);
      }
    }, 60000);
  });
}
