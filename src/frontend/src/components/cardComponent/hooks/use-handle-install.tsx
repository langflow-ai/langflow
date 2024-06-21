import { useState } from "react";
import { getComponent } from "../../../controllers/API";
import useFlowsManagerStore from "../../../stores/flowsManagerStore";
import cloneFlowWithParent from "../../../utils/storeUtils";

const useInstallComponent = (
  data,
  name,
  isStore,
  downloadsCount,
  setDownloadsCount,
  setLoading,
  setSuccessData,
  setErrorData,
) => {
  const addFlow = useFlowsManagerStore((state) => state.addFlow);

  const handleInstall = () => {
    const temp = downloadsCount;
    setDownloadsCount((old) => Number(old) + 1);
    setLoading(true);

    getComponent(data.id)
      .then((res) => {
        const newFlow = cloneFlowWithParent(res, res.id, data.is_component);
        addFlow(true, newFlow)
          .then((id) => {
            setSuccessData({
              title: `${name} ${isStore ? "Downloaded" : "Installed"} Successfully.`,
            });
            setLoading(false);
          })
          .catch((error) => {
            setLoading(false);
            setErrorData({
              title: `Error ${isStore ? "downloading" : "installing"} the ${name}`,
              list: [error.response.data.detail],
            });
          });
      })
      .catch((err) => {
        setLoading(false);
        setErrorData({
          title: `Error ${isStore ? "downloading" : "installing"} the ${name}`,
          list: [err.response.data.detail],
        });
        setDownloadsCount(temp);
      });
  };

  return { handleInstall };
};

export default useInstallComponent;
