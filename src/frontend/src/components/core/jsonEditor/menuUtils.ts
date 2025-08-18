import { faCopy } from "@fortawesome/free-solid-svg-icons";
import { type MenuItem, Mode } from "vanilla-jsoneditor";

export const filterTextModeItems = (items: MenuItem[]): MenuItem[] => {
  return items.filter((item) => {
    if (item.type === "button" && item.title) {
      const title = item.title.toLowerCase();
      // Remove search buttons in text mode only
      if (title.includes("search") || title.includes("find")) {
        return false;
      }
    }
    return true;
  });
};

export const hasCopyButton = (items: MenuItem[]): boolean => {
  return items.some(
    (item) =>
      item.type === "button" && item.title?.toLowerCase().includes("copy"),
  );
};

export const createCopyButton = (
  getEditor: () => any,
  setSuccessData: (data: { title: string }) => void,
  setErrorData: (data: { title: string; list: string[] }) => void,
): MenuItem => {
  return {
    type: "button" as const,
    onClick: () => {
      const editor = getEditor();
      if (!editor) {
        setErrorData({
          title: "Copy Failed",
          list: ["Editor not available"],
        });
        return;
      }

      const currentContent = editor.get();
      const textContent =
        "text" in currentContent
          ? currentContent.text
          : JSON.stringify(currentContent.json, null, 2);
      navigator.clipboard
        .writeText(textContent)
        .then(() => {
          setSuccessData({ title: "JSON copied to clipboard" });
        })
        .catch(() => {
          setErrorData({
            title: "Copy Failed",
            list: ["Unable to copy to clipboard. Please copy manually."],
          });
        });
    },
    icon: faCopy,
    title: "Copy JSON to clipboard",
  };
};

export const addCopyButtonToItems = (
  items: MenuItem[],
  copyButton: MenuItem,
): MenuItem[] => {
  const updatedItems = [...items];
  updatedItems.push({ type: "separator" as const });
  updatedItems.push(copyButton);
  return updatedItems;
};

export const enhanceExistingCopyButtons = (
  items: MenuItem[],
  setSuccessData: (data: { title: string }) => void,
  successMessage: string = "JSON copied to clipboard",
): MenuItem[] => {
  return items.map((item) => {
    if (item.type === "button" && item.title?.toLowerCase().includes("copy")) {
      const originalOnClick = item.onClick;
      return {
        ...item,
        onClick: (event: MouseEvent) => {
          // Call the original copy function
          if (originalOnClick) {
            originalOnClick(event);
          }
          // Add our success notification
          setSuccessData({ title: successMessage });
        },
      };
    }
    return item;
  });
};

export const processTextModeItems = (
  items: MenuItem[],
  getEditor: () => any,
  setSuccessData: (data: { title: string }) => void,
  setErrorData: (data: { title: string; list: string[] }) => void,
): MenuItem[] => {
  let filteredItems = filterTextModeItems(items);

  if (!hasCopyButton(filteredItems)) {
    const copyButton = createCopyButton(
      getEditor,
      setSuccessData,
      setErrorData,
    );
    filteredItems = addCopyButtonToItems(filteredItems, copyButton);
  } else {
    filteredItems = enhanceExistingCopyButtons(filteredItems, setSuccessData);
  }

  return filteredItems;
};

export const processTreeModeItems = (
  items: MenuItem[],
  setSuccessData: (data: { title: string }) => void,
): MenuItem[] => {
  return enhanceExistingCopyButtons(
    items,
    setSuccessData,
    "Copied to clipboard",
  );
};
