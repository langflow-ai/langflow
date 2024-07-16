import { useMutationFunctionType } from "@/types/api";
import { FlowStyleType, FlowType } from "@/types/flow";
import { AxiosResponse } from "axios";
import { ReactFlowJsonObject } from "reactflow";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPatchUpdateComponent {
    newFlow: {
        name?: string;
        data: ReactFlowJsonObject | null;
        description?: string;
        style?: FlowStyleType;
        is_component?: boolean;
        parent?: string;
        last_tested_version?: string;
      };
      tags: string[];
      publicFlow: boolean;
      id: string;
}

export const usePatchUpdateFlowStore: useMutationFunctionType<
  IPatchUpdateComponent
> = (options) => {
  const { mutate } = UseRequestProcessor();

  const patchComponent = async (
    payload: IPatchUpdateComponent,
  ): Promise<AxiosResponse<FlowType>> => {
    const { id } = payload;
    return await api.patch<FlowType>(`${getURL("STORE")}/components/${id}`);
  };

  const mutation = mutate(["usePatchUpdateFlowStore"], patchComponent, options);

  return mutation;
};
