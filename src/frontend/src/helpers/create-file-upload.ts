import { DEFAULT_FILE_PICKER_TIMEOUT } from "@/constants/constants";

export function createFileUpload(props?: {
  accept?: string;
  multiple?: boolean;
  webkitdirectory?: boolean;
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
    input.setAttribute("data-testid", "hidden-file-input");

    // Enable folder selection if webkitdirectory is true
    if (props?.webkitdirectory) {
      (
        input as HTMLInputElement & { webkitdirectory?: boolean }
      ).webkitdirectory = true;
      input.multiple = true; // webkitdirectory requires multiple to be true
    }

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

      let files = Array.from((event.target as HTMLInputElement).files || []);

      // Filter out hidden files and folders entirely when using folder selection
      if (props?.webkitdirectory) {
        // Early exit if too many files (likely includes hidden directories)
        if (files.length > 1000) {
          console.warn(
            `Too many files detected (${files.length}). This likely includes hidden directories like .mypy_cache, .git, etc. Please select a folder without large hidden directories, or clean up hidden directories first.`,
          );
          cleanup();
          resolve([]);
          return;
        }
        const originalCount = files.length;

        files = files.filter((file) => {
          const path = file.webkitRelativePath;
          const pathParts = path.split("/");

          // Multiple approaches to catch hidden files/folders:

          // 1. Check if path contains .mypy_cache specifically
          if (path.includes(".mypy_cache")) {
            return false;
          }

          // 2. Check if any path part starts with '.'
          const hasHiddenPath = pathParts.some((part) => {
            const startsWithDot = part.startsWith(".") && part.length > 0;
            return startsWithDot;
          });

          if (hasHiddenPath) {
            return false;
          }

          // 3. Additional check for common hidden patterns
          const hiddenPatterns = [
            ".DS_Store",
            ".git",
            ".vscode",
            ".idea",
            "__pycache__",
            ".pytest_cache",
            "node_modules",
          ];
          const hasHiddenPattern = hiddenPatterns.some((pattern) =>
            path.includes(pattern),
          );

          if (hasHiddenPattern) {
            return false;
          }

          return true;
        });
      }

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
