export function createFileUpload(props?: {
  accept?: string;
  multiple?: boolean;
}): Promise<File[]> {
  // Store the input element and promise resolver at module level
  let inputElement: HTMLInputElement | null = null;
  let resolvePromise: ((files: File[]) => void) | null = null;
  let isResolved = false;

  const cleanup = () => {
    if (inputElement && document.body.contains(inputElement)) {
      try {
        document.body.removeChild(inputElement);
      } catch (error) {
        console.warn("Error removing input element:", error);
      }
    }
    window.removeEventListener("focus", handleFocus);
    inputElement = null;
    resolvePromise = null;
  };

  const handleChange = (e: Event) => {
    if (!isResolved && resolvePromise) {
      isResolved = true;
      const files = Array.from((e.target as HTMLInputElement).files!);
      cleanup();
      resolvePromise(files);
    }
  };

  const handleFocus = () => {
    setTimeout(() => {
      if (!isResolved && resolvePromise) {
        isResolved = true;
        cleanup();
        resolvePromise([]);
      }
    }, 300);
  };

  // This function creates and triggers the input element
  const triggerFileInput = (): Promise<File[]> => {
    return new Promise((resolve) => {
      resolvePromise = resolve;

      inputElement = document.createElement("input");
      inputElement.type = "file";
      inputElement.accept = props?.accept ?? ".json";
      inputElement.multiple = props?.multiple ?? true;
      inputElement.style.display = "none";

      inputElement.addEventListener("change", handleChange);
      window.addEventListener("focus", handleFocus);

      document.body.appendChild(inputElement);
      inputElement.click();

      // Fallback timeout
      setTimeout(() => {
        if (!isResolved && resolvePromise) {
          isResolved = true;
          cleanup();
          resolvePromise([]);
        }
      }, 60000);
    });
  };

  // Return the trigger function instead of immediately executing it
  return triggerFileInput();
}
