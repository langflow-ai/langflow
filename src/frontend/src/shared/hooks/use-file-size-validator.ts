import { useTranslation } from "react-i18next";
import { useUtilityStore } from "@/stores/utilityStore";
import { formatFileSize } from "@/utils/stringManipulation";

const useFileSizeValidator = () => {
  const { t } = useTranslation();
  const maxFileSizeUpload = useUtilityStore((state) => state.maxFileSizeUpload);

  const validateFileSize = (file) => {
    if (file.size > maxFileSizeUpload) {
      throw new Error(
        t("errors.fileTooLarge", {
          maxSizeMB: formatFileSize(maxFileSizeUpload),
        }),
      );
    }
    return true;
  };

  return { validateFileSize };
};

export default useFileSizeValidator;
