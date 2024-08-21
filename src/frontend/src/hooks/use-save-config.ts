import useFlowsManagerStore from "@/stores/flowsManagerStore";
import axios from "axios";
import { useEffect } from "react";
import { useGetConfigQuery } from "../controllers/API/queries/config/use-get-config";

function useSaveConfig() {
  const { data } = useGetConfigQuery();
  const setAutoSaving = useFlowsManagerStore((state) => state.setAutoSaving);
  const setAutoSavingInterval = useFlowsManagerStore(
    (state) => state.setAutoSavingInterval,
  );

  useEffect(() => {
    if (data) {
      const timeoutInMilliseconds = data.frontend_timeout
        ? data.frontend_timeout * 1000
        : 30000;
      axios.defaults.baseURL = "";
      axios.defaults.timeout = timeoutInMilliseconds;
      setAutoSaving(data.auto_saving);
      setAutoSavingInterval(data.auto_saving_interval);
    }
  }, [data]);
}

export default useSaveConfig;
