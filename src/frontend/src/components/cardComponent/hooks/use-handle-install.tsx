import { useState } from "react";
import { getComponent } from "../../../controllers/API";
import useFlowsManagerStore from "../../../stores/flowsManagerStore";
import { storeComponent } from "../../../types/store";
import cloneFlowWithParent from "../../../utils/storeUtils";
import { useTranslation } from "react-i18next";

const useInstallComponent = (
  data: storeComponent,
  name: string,
  isStore: boolean,
  downloadsCount: number,
  setDownloadsCount: (value: any) => void,
  setLoading: (value: boolean) => void,
  setSuccessData: (value: { title: string }) => void,
  setErrorData: (value: { title: string; list: string[] }) => void,
) => {

  const { t } = useTranslation();

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
              title: `${t("{{name}} {{action}} Successfully.", {
                action: isStore ? t("Downloaded") : t("Installed"),
                name: name
              })}`
            });
            setLoading(false);
          })
          .catch((error) => {
            setLoading(false);
            setErrorData({
              title: `${t("Error {{action}} the {{name}}", {
                action: isStore ? t("downloading") : t("installing"),
                name: name
              })}`,
              list: [error.response.data.detail],
            });
          });
      })
      .catch((err) => {
        setLoading(false);
        setErrorData({
          title:  `${t("Error {{action}} the {{name}}", {
            action: isStore ? t("downloading") : t("installing"),
            name: name
          })}`,
          list: [err.response.data.detail],
        });
        setDownloadsCount(temp);
      });
  };

  return { handleInstall };
};

export default useInstallComponent;
