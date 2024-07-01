import { useEffect } from "react";
import { VertexBuildTypeAPI } from "../../types/api";
import { isErrorLog } from "../../types/utils/typeCheckingUtils";

const useValidationStatusString = (
  validationStatus: VertexBuildTypeAPI | null,
  setValidationString: (value: any) => void,
) => {
  useEffect(() => {
    if (validationStatus && validationStatus.data?.outputs) {
      // if it is not a string turn it into a string
      let newValidationString = "";
      Object.values(validationStatus?.data?.outputs).forEach((output: any) => {
        if (isErrorLog(output)) {
          newValidationString += `${output.message.errorMessage}\n`;
        }
      });
      setValidationString(newValidationString);
    }
  }, [validationStatus, validationStatus?.data?.outputs, setValidationString]);
};

export default useValidationStatusString;
