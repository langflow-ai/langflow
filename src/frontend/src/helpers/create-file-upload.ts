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
    
    // Enable folder selection if webkitdirectory is true
    if (props?.webkitdirectory) {
      (input as any).webkitdirectory = true;
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
        const originalCount = files.length;
        
        // First, let's see what we're dealing with
        console.log('Before filtering - sample paths:', files.slice(0, 5).map(f => f.webkitRelativePath));
        
        files = files.filter(file => {
          const pathParts = file.webkitRelativePath.split('/');
          
          // Filter out any file that has a hidden directory or file anywhere in its path
          // This will exclude:
          // - .DS_Store (hidden file)
          // - .mypy_cache/anything (files inside hidden directories)
          // - some/path/.hidden/file.txt (files inside nested hidden directories)
          const hasHiddenPath = pathParts.some(part => 
            part.startsWith('.') && part.length > 0
          );
          
          if (hasHiddenPath) {
            console.log('Filtering out hidden path:', file.webkitRelativePath);
          }
          
          return !hasHiddenPath;
        });
        
        // Debug logging for folder selection
        console.log('Folder selection results:');
        console.log(`Total files found: ${originalCount}, after filtering hidden files/folders: ${files.length}`);
        if (files.length > 0) {
          console.log('Remaining files (first 5):', files.slice(0, 5).map(f => ({
            name: f.name,
            webkitRelativePath: f.webkitRelativePath,
            size: f.size
          })));
        }
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
