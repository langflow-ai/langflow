import { INVALID_FILE_SIZE_ALERT } from "@/constants/alerts_constants";
import { useUtilityStore } from "@/stores/utilityStore";

const useFileSizeValidator = (
  setErrorData: (newState: { title: string; list?: Array<string> }) => void,
) => {
  const maxFileSizeUpload = useUtilityStore((state) => state.maxFileSizeUpload);

  const validateFileSize = (file) => {
    if (file.size > maxFileSizeUpload) {
      setErrorData({
        title: INVALID_FILE_SIZE_ALERT(maxFileSizeUpload / 1024 / 1024),
      });
      return false;
    }
    return true;
  };

  return { validateFileSize };
};

export default useFileSizeValidator;
