import { useEffect } from "react";
import { LogType, VertexBuildTypeAPI } from "../../types/api";

const useValidationStatusString = (validationStatus: VertexBuildTypeAPI, setValidationString) => {
  useEffect(() => {
    if (validationStatus?.data?.logs) {
      // if it is not a string turn it into a string
      console.log("validationStatus", validationStatus);
      let newValidationString = "";
      Object.values(validationStatus?.data?.logs).forEach((log: LogType | LogType[]) => {
        if (!Array.isArray(log)) {
          log = [log];
        }
        log.forEach((logItem) => {
          if (logItem.type === "error" || logItem.type === "ValueError") {
            newValidationString += `${logItem.message}\n`;
          }
        });
      });
      setValidationString(newValidationString);
    }
  }, [validationStatus, validationStatus?.data?.logs, setValidationString]);
};

export default useValidationStatusString;
