import { ENABLE_LANGFLOW_STORE } from "@/customization/feature-flags";
import { useUtilityStore } from "@/stores/utilityStore";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface ITagsDataArray {
  id: string;
  name: string;
}

type tagsQueryResponse = Array<ITagsDataArray>;

export const useGetTagsQuery: useQueryFunctionType<
  undefined,
  tagsQueryResponse
> = (options) => {
  const { query } = UseRequestProcessor();
  const setTags = useUtilityStore((state) => state.setTags);

  const getTagsFn = async () => {
    return await api.get<tagsQueryResponse>(`${getURL("STORE")}/tags`);
  };

  const responseFn = async () => {
    const { data } = await getTagsFn();
    setTags(data);
    return data;
  };

  const queryResult = query(["useGetTagsQuery"], responseFn, {
    refetchOnWindowFocus: false,
    ...options,
    // Gated here, not at the call site: AppInitPage fires this on every app boot.
    enabled: (options?.enabled ?? true) && ENABLE_LANGFLOW_STORE,
  });

  return queryResult;
};
