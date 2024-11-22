import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useTypesStore } from "@/stores/typesStore";
import { APIObjectType, useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetTypes: useQueryFunctionType<undefined> = (options) => {
  const { query } = UseRequestProcessor();
  const setLoading = useFlowsManagerStore((state) => state.setIsLoading);
  const setTypes = useTypesStore((state) => state.setTypes);

  const getTypesFn = async () => {
    try {
      const response = await api.get<APIObjectType>(
        `${getURL("ALL")}?force_refresh=true`,
      );
      const data = response?.data;
      setTypes(data);
      return data;
    } catch {
      (error) => {
        console.error("An error has occurred while fetching types.");
        console.log(error);
        setLoading(false);
        throw error;
      };
    }
  };

  const queryResult = query(["useGetTypes"], getTypesFn, {
    refetchOnWindowFocus: false,
    ...options,
  });

  return queryResult;
};
