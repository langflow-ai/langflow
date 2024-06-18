import { useEffect } from "react";
import { LogType, VertexBuildTypeAPI } from "../../types/api";

const useValidationStatusString = (validationStatus: VertexBuildTypeAPI, setValidationString) => {
  useEffect(() => {
    if (validationStatus?.data?.logs) {
      // if it is not a string turn it into a string
      console.log("validationStatus", validationStatus);
      let newValidationString = "";
      Object.values(validationStatus?.data?.logs).forEach((log: any) => {
          if (log.type === "error" || log.type === "ValueError") {
            newValidationString += `${log.message}\n`;
          }
      });
      setValidationString(newValidationString);
    }
  }, [validationStatus, validationStatus?.data?.logs, setValidationString]);
};

export default useValidationStatusString;
