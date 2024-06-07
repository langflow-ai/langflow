import { useEffect } from "react";

const useValidationStatusString = (validationStatus, setValidationString) => {
  useEffect(() => {
    if (validationStatus?.data.logs) {
      // if it is not a string turn it into a string
      let newValidationString = "";
      if (Array.isArray(validationStatus.data.logs)) {
        newValidationString = validationStatus.data.logs
          .map((log) => (log?.message ? log.message : JSON.stringify(log)))
          .join("\n");
      }
      if (typeof newValidationString !== "string") {
        newValidationString = JSON.stringify(validationStatus.data.logs);
      }

      setValidationString(newValidationString);
    }
  }, [validationStatus, validationStatus?.data.logs, setValidationString]);
};

export default useValidationStatusString;
