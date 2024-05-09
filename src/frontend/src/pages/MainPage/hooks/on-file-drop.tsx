import {
  CONSOLE_ERROR_MSG,
  UPLOAD_ALERT_LIST,
  WRONG_FILE_ERROR_ALERT,
} from "../../../constants/alerts_constants";
import useAlertStore from "../../../stores/alertStore";
import useFlowsManagerStore from "../../../stores/flowsManagerStore";

const useFileDrop = (uploadFlow, is_component) => {
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const flows = useFlowsManagerStore((state) => state.flows);
  const setAllFlows = useFlowsManagerStore((state) => state.setAllFlows);

  const handleFileDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.types.some((type) => type === "Files")) {
      if (e.dataTransfer.files.item(0).type === "application/json") {
        uploadFlow({
          newProject: true,
          file: e.dataTransfer.files.item(0),
          isComponent: is_component,
        })
          .then(() => {
            setSuccessData({
              title: `${
                is_component ? "Component" : "Flow"
              } uploaded successfully`,
            });
            setAllFlows(flows);
          })
          .catch((error) => {
            setErrorData({
              title: CONSOLE_ERROR_MSG,
              list: [error],
            });
          });
      } else {
        setErrorData({
          title: WRONG_FILE_ERROR_ALERT,
          list: [UPLOAD_ALERT_LIST],
        });
      }
    }
  };

  return [handleFileDrop];
};

export default useFileDrop;
