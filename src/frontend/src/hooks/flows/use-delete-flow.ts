import { useDeleteDeleteFlows } from "@/controllers/API/queries/flows/use-delete-delete-flows";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useTypesStore } from "@/stores/typesStore";
import {
  extractFieldsFromComponenents,
  processFlows,
} from "@/utils/reactflowUtils";

const useDeleteFlow = () => {
  const { t } = useTranslation();
  const setFlows = useFlowsManagerStore((state) => state.setFlows);

  const { mutate, isPending } = useDeleteDeleteFlows();

  const deleteFlow = async ({
    id,
  }: {
    id: string | string[];
  }): Promise<void> => {
    return new Promise<void>((resolve, reject) => {
      if (!Array.isArray(id)) {
        id = [id];
      }
      const revisions = Object.fromEntries(
        (useFlowsManagerStore.getState().flows ?? [])
          .filter((flow) => id.includes(flow.id))
          .flatMap((flow) =>
            typeof flow.edit_revision === "number"
              ? ([[flow.id, flow.edit_revision]] as const)
              : [],
          ),
      );
      if (Object.keys(revisions).length !== id.length) {
        reject(new Error(t("errors.workflowRevisionUnavailable")));
        return;
      }
      mutate(
        { flow_ids: id, expected_edit_revision: revisions },
        {
          onSuccess: () => {
            // Fresh read: a pre-mutation snapshot would drop flows created
            // while the DELETE was in flight, bouncing FlowPage to /all.
            const flows = useFlowsManagerStore.getState().flows;
            const { data, flows: myFlows } = processFlows(
              (flows ?? []).filter((flow) => !id.includes(flow.id)),
            );
            setFlows(myFlows);
            useTypesStore.setState((state) => ({
              data: { ...state.data, ["saved_components"]: data },
              ComponentFields: extractFieldsFromComponenents({
                ...state.data,
                ["saved_components"]: data,
              }),
            }));

            resolve();
          },
          onError: (e) => reject(e),
        },
      );
    });
  };

  return { deleteFlow, isDeleting: isPending };
};

export default useDeleteFlow;

import { useTranslation } from "react-i18next";
