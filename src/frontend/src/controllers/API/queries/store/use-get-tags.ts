import { useQueryFunctionType } from "@/types/api";
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
> = (_, options) => {
  const { query } = UseRequestProcessor();

  const getTagsFn = async () => {
    return await api.get<tagsQueryResponse>(`${getURL("STORE")}/tags`);
  };

  const responseFn = async () => {
    const { data } = await getTagsFn();
    return data;
  };

  const queryResult = query(["useGetTagsQuery"], responseFn, { ...options });

  return queryResult;
};
