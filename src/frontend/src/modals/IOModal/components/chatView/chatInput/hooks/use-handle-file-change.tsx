import ShortUniqueId from "short-unique-id";
import useFileUpload from "./use-file-upload";

export const useHandleFileChange = (setFiles, currentFlowId) => {
  const handleFileChange = async (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const file = event.target.files?.[0];
    if (file) {
      const uid = new ShortUniqueId({ length: 3 });
      const id = uid();
      const type = file.type.split("/")[0];
      const blob = file;

      setFiles((prevFiles) => [
        ...prevFiles,
        { file: blob, loading: true, error: false, id, type },
      ]);

      useFileUpload(blob, currentFlowId, setFiles, id);
    }
  };

  return {
    handleFileChange,
  };
};

export default useHandleFileChange;
