import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useCreateDatasetFromExample } from "@/controllers/API/queries/evals/use-datasets";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useAlertStore from "@/stores/alertStore";
import { extractApiErrorMessages } from "@/utils/apiError";

/** Adds a ready-made dataset and opens it; `pendingKey` names the example being added. */
export function useAddExampleDataset() {
  const { t } = useTranslation();
  const navigate = useCustomNavigate();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const [pendingKey, setPendingKey] = useState<string | null>(null);
  const createFromExample = useCreateDatasetFromExample({
    onSuccess: (dataset) => navigate(`/assets/datasets/${dataset.id}`),
    onError: (error) =>
      setErrorData({
        title: t("evals.datasets.createError"),
        list: extractApiErrorMessages(error),
      }),
    onSettled: () => setPendingKey(null),
  });

  const add = (key: string) => {
    if (pendingKey) return;
    setPendingKey(key);
    createFromExample.mutate({ key });
  };

  return { add, pendingKey };
}
