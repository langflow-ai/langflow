import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useTypesStore } from "@/stores/typesStore";
import type { APIObjectType, useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetTypes: useQueryFunctionType<
  undefined,
  any,
  { checkCache?: boolean }
> = (options) => {
  const { query } = UseRequestProcessor();
  const setLoading = useFlowsManagerStore((state) => state.setIsLoading);
  const setTypes = useTypesStore((state) => state.setTypes);

  const getTypesFn = async (checkCache = false) => {
    try {
      if (checkCache) {
        const data = useTypesStore.getState().types;
        if (data && Object.keys(data).length > 0) {
          return data;
        }
      }

      const response = await api.get<APIObjectType>(
        `${getURL("ALL")}?force_refresh=true`,
      );
      const data = response?.data;
      setTypes(data);
      return data;
    } catch (error) {
      console.error("[Types] Error fetching types:", error);
      setLoading(false);
      throw error;
    }
  };

  const queryResult = query(
    ["useGetTypes"],
    () => getTypesFn(options?.checkCache),
    {
      refetchOnWindowFocus: false,
      ...options,
    },
  );

  return queryResult;
};
