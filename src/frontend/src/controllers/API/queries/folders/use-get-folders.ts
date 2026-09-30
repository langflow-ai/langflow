import type { ProjectListType } from "@/pages/MainPage/entities";
import useAuthStore from "@/stores/authStore";
import { useFolderStore } from "@/stores/foldersStore";
import { useUtilityStore } from "@/stores/utilityStore";
import type { useQueryFunctionType } from "@/types/api";
import { getDefaultProjectId } from "@/utils/project-display-name";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetFoldersQuery: useQueryFunctionType<
  undefined,
  ProjectListType[]
> = (options) => {
  const { query } = UseRequestProcessor();

  const setMyCollectionId = useFolderStore((state) => state.setMyCollectionId);
  const setFolders = useFolderStore((state) => state.setFolders);
  const defaultFolderName = useUtilityStore((state) => state.defaultFolderName);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  const getFoldersFn = async (): Promise<ProjectListType[]> => {
    const res = await api.get<ProjectListType[]>(`${getURL("PROJECTS")}/`);
    const data = res.data;

    const myCollectionId = getDefaultProjectId(data, defaultFolderName);
    setMyCollectionId(myCollectionId);
    setFolders(data);

    return data;
  };

  const queryResult = query(["useGetFolders"], getFoldersFn, {
    ...options,
    enabled: isAuthenticated && (options?.enabled ?? true),
  });
  return queryResult;
};
