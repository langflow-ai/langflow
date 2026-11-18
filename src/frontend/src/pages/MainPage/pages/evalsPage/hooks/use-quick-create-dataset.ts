import { isAxiosError } from "axios";
import { useTranslation } from "react-i18next";
import type { Dataset } from "@/controllers/API/queries/evals/types";
import { useCreateDataset } from "@/controllers/API/queries/evals/use-datasets";
import useAlertStore from "@/stores/alertStore";
import { extractApiErrorMessages } from "@/utils/apiError";
import { uniqueName } from "../utils/unique-name";

// The list on screen may not hold every dataset, so a taken name can still come back as a conflict.
const MAX_ATTEMPTS = 5;

/** Creates a dataset in one step: the name is `base`, made unique against the names already known. */
export function useQuickCreateDataset(existingNames: readonly string[]) {
  const { t } = useTranslation();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const createDataset = useCreateDataset();

  const createUnique = async (base: string): Promise<Dataset | null> => {
    const taken = [...existingNames];
    for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt += 1) {
      const name = uniqueName(base, taken);
      try {
        return await createDataset.mutateAsync({ name });
      } catch (error) {
        const conflict = isAxiosError(error) && error.response?.status === 409;
        if (!conflict || attempt === MAX_ATTEMPTS) {
          setErrorData({
            title: t("evals.datasets.createError"),
            list: extractApiErrorMessages(error),
          });
          return null;
        }
        taken.push(name);
      }
    }
    return null;
  };

  return { createUnique, isPending: createDataset.isPending };
}
