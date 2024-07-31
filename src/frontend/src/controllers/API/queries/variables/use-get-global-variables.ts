import { useGlobalVariablesStore } from "@/stores/globalVariablesStore/globalVariables";
import { useMutationFunctionType } from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

type GlobalVariable = {
  id: string;
  type: string;
  default_fields: string[];
  name: string;
};

export const useGetGlobalVariables: useMutationFunctionType<undefined, void> = (
  options?,
) => {
  const { mutate } = UseRequestProcessor();

  const setGlobalVariables = useGlobalVariablesStore(
    (state) => state.setGlobalVariables,
  );

  const getGlobalVariables = async (): Promise<[GlobalVariable]> => {
    const res = await api.get(`${getURL("VARIABLES")}/`);
    return res.data;
  };

  const getGlobalVariablesFn = async (): Promise<{
    [key: string]: GlobalVariable;
  }> => {
    const data = await getGlobalVariables();
    const globalVariables = {};

    data?.forEach((element) => {
      globalVariables[element.name] = {
        id: element.id,
        type: element.type,
        default_fields: element.default_fields,
      };
    });

    setGlobalVariables(globalVariables);
    return globalVariables;
  };

  const mutation: UseMutationResult<any, any, any> = mutate(
    ["useGetGlobalVariables"],
    getGlobalVariablesFn,
    options,
  );

  return mutation;
};
