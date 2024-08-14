import useUploadFlow from "@/hooks/flows/use-upload-flow";
import { CONSOLE_ERROR_MSG } from "../../../constants/alerts_constants";
import useAlertStore from "../../../stores/alertStore";

const useFileDrop = (type?: string) => {
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const uploadFlow = useUploadFlow();

  const handleFileDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.types.every((type) => type === "Files")) {
      const files: File[] = Array.from(e.dataTransfer.files);
      uploadFlow({
        files,
        isComponent:
          type === "component" ? true : type === "flow" ? false : undefined,
      })
        .then(() => {
          setSuccessData({
            title: `All files uploaded successfully`,
          });
        })
        .catch((error) => {
          console.log(error);
          setErrorData({
            title: CONSOLE_ERROR_MSG,
            list: [(error as Error).message],
          });
        });
    }
  };
  return handleFileDrop;
};

export default useFileDrop;
