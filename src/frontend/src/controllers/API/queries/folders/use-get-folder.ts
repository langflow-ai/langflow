import { FolderType } from "@/pages/MainPage/entities";
import { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IGetFolder {
  id: string;
}

export const useGetFolderQuery: useQueryFunctionType<IGetFolder, FolderType> = (
  params,
  options,
) => {
  const { query } = UseRequestProcessor();

  const getFolderFn = async (): Promise<FolderType> => {
    const res = await api.get(`${getURL("FOLDERS")}/${params.id}`);
    const data = res.data;

    return data;
  };

  const queryResult = query(
    ["useGetFolder", { id: params.id }],
    getFolderFn,
    options,
  );
  return queryResult;
};
