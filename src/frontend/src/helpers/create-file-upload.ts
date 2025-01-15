let globalInput: HTMLInputElement | null = null;
let activePromiseResolve: ((files: File[]) => void) | null = null;
let isListening = false;

const setupGlobalInput = (props?: { accept?: string; multiple?: boolean }) => {
  if (!globalInput) {
    globalInput = document.createElement("input");
    globalInput.type = "file";
    globalInput.style.display = "none";
    document.body.appendChild(globalInput);
  }

  globalInput.accept = props?.accept ?? ".json";
  globalInput.multiple = props?.multiple ?? true;

  if (!isListening) {
    const handleChange = (e: Event) => {
      const files = Array.from((e.target as HTMLInputElement).files || []);
      if (activePromiseResolve) {
        activePromiseResolve(files);
        activePromiseResolve = null;
      }
      if (globalInput) {
        globalInput.value = "";
      }
    };

    globalInput.addEventListener("change", handleChange);
    isListening = true;
  }
};

export function createFileUpload(props?: {
  accept?: string;
  multiple?: boolean;
}): Promise<File[]> {
  return new Promise((resolve) => {
    setupGlobalInput(props);

    activePromiseResolve = resolve;

    setTimeout(() => {
      if (globalInput && document.body.contains(globalInput)) {
        globalInput.click();
      } else {
        resolve([]);
      }
    }, 0);

    setTimeout(() => {
      if (activePromiseResolve === resolve) {
        activePromiseResolve = null;
        resolve([]);
      }
    }, 30000);
  });
}
