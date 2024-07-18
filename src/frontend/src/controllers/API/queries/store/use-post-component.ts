import { useMutationFunctionType } from "@/types/api";
import { FlowStyleType } from "@/types/flow";
import { ReactFlowJsonObject } from "reactflow";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostComponentProps {
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
}

export const usePostComponent: useMutationFunctionType<IPostComponentProps> = (
  options,
) => {
  const { mutate } = UseRequestProcessor();

  const postComponent = async (payload: IPostComponentProps): Promise<any> => {
    const {
      publicFlow,
      tags,
      newFlow: {
        name,
        data,
        description,
        is_component,
        parent,
        last_tested_version,
      },
    } = payload;
    const newComponent = {
      name: name,
      data: data,
      description: description,
      is_component: is_component,
      parent: parent,
      tags: tags,
      private: !publicFlow,
      status: publicFlow ? "Public" : "Private",
      last_tested_version: last_tested_version,
    };
    return await api.post<any>(`${getURL("STORE")}/components/`, newComponent);
  };

  const mutation = mutate(["usePostComponent"], postComponent, options);

  return mutation;
};
