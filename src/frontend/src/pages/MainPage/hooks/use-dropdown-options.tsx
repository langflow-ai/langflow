import useUploadFlow from "@/hooks/flows/use-upload-flow";
import { CONSOLE_ERROR_MSG } from "../../../constants/alerts_constants";
import useAlertStore from "../../../stores/alertStore";

const useDropdownOptions = ({
  navigate,
  is_component,
}: {
  navigate: (url: string) => void;
  is_component: boolean;
}) => {
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const uploadFlow = useUploadFlow();
  const handleImportFromJSON = () => {
    uploadFlow({
      isComponent: is_component,
    })
      .then((id) => {
        setSuccessData({
          title: `${is_component ? "Component" : "Flow"} uploaded successfully`,
        });
        if (!is_component) navigate("/flow/" + id);
      })
      .catch((error) => {
        setErrorData({
          title: CONSOLE_ERROR_MSG,
          list: [error],
        });
      });
  };

  const dropdownOptions = [
    {
      name: "Import from JSON",
      onBtnClick: handleImportFromJSON,
    },
  ];

  return [...dropdownOptions];
};

export default useDropdownOptions;
