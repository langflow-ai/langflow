import { INVALID_FILE_SIZE_ALERT } from "@/constants/alerts_constants";
import { useUtilityStore } from "@/stores/utilityStore";
import { formatFileSize } from "@/utils/stringManipulation";

const useFileSizeValidator = () => {
  const maxFileSizeUpload = useUtilityStore((state) => state.maxFileSizeUpload);

  const validateFileSize = (file) => {
    if (file.size > maxFileSizeUpload) {
      throw new Error(
        INVALID_FILE_SIZE_ALERT(formatFileSize(maxFileSizeUpload)),
      );
    }
    return true;
  };

  return { validateFileSize };
};

export default useFileSizeValidator;
