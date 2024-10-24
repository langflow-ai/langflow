import { DEFAULT_FOLDER, STARTER_FOLDER_NAME } from "@/constants/constants";
import { FolderType } from "@/pages/MainPage/entities";
import useAuthStore from "@/stores/authStore";
import { useFolderStore } from "@/stores/foldersStore";
import { useTypesStore } from "@/stores/typesStore";
import { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { useGetRefreshFlows } from "../flows/use-get-refresh-flows";

export const useGetFoldersQuery: useQueryFunctionType<
  undefined,
  FolderType[]
> = (options) => {
  const { query } = UseRequestProcessor();
  const { mutateAsync: refreshFlows } = useGetRefreshFlows();

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
    const { getTypes, types } = useTypesStore.getState();

    await refreshFlows({ get_all: true, header_flows: true });
    if (!types || Object.keys(types).length === 0) await getTypes();

    return data;
  };

  const queryResult = query(["useGetFolders"], getFoldersFn, options);
  return queryResult;
};
