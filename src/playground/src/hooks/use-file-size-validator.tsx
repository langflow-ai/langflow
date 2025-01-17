import { usePlaygroundStore } from "src/stores/playgroundStore";

const useFileSizeValidator = (
  setErrorData?: (error: string) => void,
) => {
  const maxFileSizeUpload = usePlaygroundStore((state) => state.maxFileSizeUpload);

  const validateFileSize = (file) => {
    if (file.size > maxFileSizeUpload) {
      setErrorData?.(file.size);
      return false;
    }
    return true;
  };

  return { validateFileSize };
};

export default useFileSizeValidator;
