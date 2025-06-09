import { DEFAULT_FILE_PICKER_TIMEOUT } from "@/constants/constants";

export const createDirectoryUpload = (): Promise<string> => {
  return new Promise(async (resolve) => {
    // Try modern File System Access API first (if available)
    if ("showDirectoryPicker" in window) {
      try {
        const dirHandle = await (window as any).showDirectoryPicker();
        resolve(dirHandle.name);
        return;
      } catch (error) {
        // User cancelled or API not supported, fall back to input method
        console.log(
          "Directory picker cancelled or not supported, falling back to input method",
        );
      }
    }

    // Fallback to traditional input method
    const input = document.createElement("input");
    input.type = "file";
    input.style.position = "fixed";
    input.style.top = "0";
    input.style.left = "0";
    input.style.opacity = "0.001";
    input.style.pointerEvents = "none";
    input.webkitdirectory = true; // Enable directory selection
    input.multiple = false; // Only single directory selection

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

      if (files.length > 0) {
        // Browser limitation: webkitRelativePath only gives relative paths from selected directory
        // NOT absolute filesystem paths (for security reasons)
        const firstFile = files[0];
        const relativePath = firstFile.webkitRelativePath;

        console.log("webkitRelativePath:", relativePath);

        // Extract directory name (this will be relative, not absolute)
        let directoryPath = "";
        if (relativePath) {
          const pathParts = relativePath.split("/");
          if (pathParts.length > 1) {
            // Remove filename, keep directory structure
            pathParts.pop();
            directoryPath = pathParts.join("/");
          } else {
            directoryPath = pathParts[0];
          }
        }

        console.log("Final directory path (relative):", directoryPath);
        console.log(
          "Note: This is a relative path, not absolute. Users should manually enter full paths.",
        );

        resolve(directoryPath);
      } else {
        resolve("");
      }
    };

    const handleFocus = () => {
      setTimeout(() => {
        if (!isHandled) {
          isHandled = true;
          cleanup();
          resolve("");
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
        resolve("");
      }
    }, DEFAULT_FILE_PICKER_TIMEOUT);
  });
};
