import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  useAddExampleToDataset,
  useCreateDatasetFromExample,
} from "@/controllers/API/queries/evals/use-datasets";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useAlertStore from "@/stores/alertStore";
import { extractApiErrorMessages } from "@/utils/apiError";

/**
 * Adds a ready-made dataset: with `datasetId` its rows fill that dataset, otherwise a new
 * dataset is created and opened. `pendingKey` names the example being added.
 */
export function useAddExampleDataset(datasetId?: string) {
  const { t } = useTranslation();
  const navigate = useCustomNavigate();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const [pendingKey, setPendingKey] = useState<string | null>(null);
  const createFromExample = useCreateDatasetFromExample();
  const fillFromExample = useAddExampleToDataset({
    datasetId: datasetId ?? "",
  });

  const fail = (title: string) => (error: unknown) =>
    setErrorData({ title, list: extractApiErrorMessages(error) });
  const settle = () => setPendingKey(null);

  const add = (key: string) => {
    if (pendingKey) return;
    setPendingKey(key);
    if (datasetId) {
      fillFromExample.mutate(
        { key },
        { onError: fail(t("evals.examples.fillError")), onSettled: settle },
      );
      return;
    }
    createFromExample.mutate(
      { key },
      {
        onSuccess: (dataset) => navigate(`/assets/datasets/${dataset.id}`),
        onError: fail(t("evals.datasets.createError")),
        onSettled: settle,
      },
    );
  };

  return { add, pendingKey };
}
