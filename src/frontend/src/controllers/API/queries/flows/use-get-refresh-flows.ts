import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useFolderStore } from "@/stores/foldersStore";
import { useTypesStore } from "@/stores/typesStore";
import { useMutationFunctionType } from "@/types/api";
import { FlowType } from "@/types/flow";
import {
  extractFieldsFromComponenents,
  processFlows,
} from "@/utils/reactflowUtils";
import { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetRefreshFlows: useMutationFunctionType<
  undefined,
  undefined
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const setExamples = useFlowsManagerStore((state) => state.setExamples);
  const setFlows = useFlowsManagerStore((state) => state.setFlows);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const starterProjectId = useFolderStore((state) => state.starterProjectId);

  const getRefreshFlowsFn = async (): Promise<void> => {
    try {
    } catch (e) {
      setErrorData({
        title: "Could not load flows from database",
      });
      throw e;
    }
    const response = await api.get<FlowType[]>(`${getURL("FLOWS")}/`);
    const dbData = response.data;
    if (dbData) {
      const { data, flows } = processFlows(dbData);
      const examples = flows.filter(
        (flow) => flow.folder_id === starterProjectId,
      );
      setExamples(examples);

      const flowsWithoutStarterFolder = flows.filter(
        (flow) => flow.folder_id !== starterProjectId,
      );

      setFlows(flowsWithoutStarterFolder);
      useTypesStore.setState((state) => ({
        data: { ...state.data, ["saved_components"]: data },
        ComponentFields: extractFieldsFromComponenents({
          ...state.data,
          ["saved_components"]: data,
        }),
      }));
      return;
    }
  };

  const mutation: UseMutationResult<void, any, undefined> = mutate(
    ["useGetRefreshFlows"],
    getRefreshFlowsFn,
    options,
  );

  return mutation;
};
