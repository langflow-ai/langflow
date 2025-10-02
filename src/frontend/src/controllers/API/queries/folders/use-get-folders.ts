import type { FolderType } from "@/pages/MainPage/entities";
import useAuthStore from "@/stores/authStore";
import { useFolderStore } from "@/stores/foldersStore";
import { useUtilityStore } from "@/stores/utilityStore";
import type { useQueryFunctionType } from "@/types/api";
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
  const defaultFolderName = useUtilityStore((state) => state.defaultFolderName);

  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  const getFoldersFn = async (): Promise<FolderType[]> => {
    if (!isAuthenticated) return [];
    const res = await api.get(`${getURL("PROJECTS")}/`);
    const data = res.data;

    const myCollectionId = data?.find((f) => f.name === defaultFolderName)?.id;
    setMyCollectionId(myCollectionId);
    setFolders(data);

    return data;
  };

  const queryResult = query(["useGetFolders"], getFoldersFn, options);
  return queryResult;
};
