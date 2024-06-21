import { useEffect } from "react";
import { VertexBuildTypeAPI } from "../../types/api";
import { isErrorLog } from "../../types/utils/typeCheckingUtils";

const useValidationStatusString = (
  validationStatus: VertexBuildTypeAPI | null,
  setValidationString,
) => {
  useEffect(() => {
    if (validationStatus && validationStatus.data?.logs) {
      // if it is not a string turn it into a string
      let newValidationString = "";
      Object.values(validationStatus?.data?.logs).forEach((log: any) => {
        if (isErrorLog(log)) {
          newValidationString += `${log.message.errorMessage}\n`;
        }
      });
      setValidationString(newValidationString);
    }
  }, [validationStatus, validationStatus?.data?.logs, setValidationString]);
};

export default useValidationStatusString;
