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
    const {
      id,
      tags,
      publicFlow,
      newFlow: {
        name,
        data,
        description,
        is_component,
        parent,
        last_tested_version,
      },
    } = payload;
    return await api.patch<FlowType>(`${getURL("STORE")}/components/${id}`, {
      name: name,
      data: data,
      description: description,
      is_component: is_component,
      parent: parent,
      tags: tags,
      private: !publicFlow,
      last_tested_version: last_tested_version,
    });
  };

  const mutation = mutate(["usePatchUpdateFlowStore"], patchComponent, options);

  return mutation;
};
