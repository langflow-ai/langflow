import { useTranslation } from "react-i18next";
import type { MenuItem, Mode } from "vanilla-jsoneditor";
import { processTextModeItems, processTreeModeItems } from "./menuUtils";

export const useMenuCustomization = (
  setSuccessData: (data: { title: string }) => void,
  setErrorData: (data: { title: string; list: string[] }) => void,
) => {
  const { t } = useTranslation();
  const messages = {
    copyFailed: t("misc.copyFailed"),
    editorNotAvailable: t("misc.editorNotAvailable"),
    jsonCopied: t("success.jsonCopied"),
    unableToCopy: t("misc.unableToCopy"),
    copyJson: t("misc.copyJson"),
    outputCopied: t("success.outputCopied"),
  };

  const customizeMenu = (
    items: MenuItem[],
    context: { mode: Mode; modal: boolean; readOnly: boolean },
    // biome-ignore lint/suspicious/noExplicitAny: legacy
    getEditor: () => any,
  ): MenuItem[] => {
    switch (context.mode) {
      case "text":
        return processTextModeItems(
          items,
          getEditor,
          setSuccessData,
          setErrorData,
          messages,
        );

      case "tree":
        return processTreeModeItems(
          items,
          setSuccessData,
          messages.outputCopied,
        );

      default:
        // For all other modes, return items unchanged
        return items;
    }
  };

  return { customizeMenu };
};
