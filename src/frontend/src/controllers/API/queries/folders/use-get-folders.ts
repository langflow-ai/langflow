import { DEFAULT_FOLDER } from "@/constants/constants";
import { FolderType } from "@/pages/MainPage/entities";
import useAuthStore from "@/stores/authStore";
import { useFolderStore } from "@/stores/foldersStore";
import { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetFoldersQuery: useQueryFunctionType<
  undefined,
  FolderType[]
> = (options) => {
  const { query } = UseRequestProcessor();

  const setMyCollectionId = useFolderStore((state) => state.setMyCollectionId);
  const setFolders = useFolderStore((state) => state.setFolders);

  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  const getFoldersFn = async (): Promise<FolderType[]> => {
    if (!isAuthenticated) return [];
    const res = await api.get(`${getURL("FOLDERS")}/`);
    const data = res.data;

    const myCollectionId = data?.find((f) => f.name === DEFAULT_FOLDER)?.id;
    setMyCollectionId(myCollectionId);
    setFolders(data);

    return data;
  };

  const queryResult = query(["useGetFolders"], getFoldersFn, options);
  return queryResult;
};
