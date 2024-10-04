import { DEFAULT_FOLDER, STARTER_FOLDER_NAME } from "@/constants/constants";
import { FolderType } from "@/pages/MainPage/entities";
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

  const setStarterProjectId = useFolderStore(
    (state) => state.setStarterProjectId,
  );
  const setMyCollectionId = useFolderStore((state) => state.setMyCollectionId);

  const getFoldersFn = async (): Promise<FolderType[]> => {
    const res = await api.get(`${getURL("FOLDERS")}/`);
    const data = res.data;

    const foldersWithoutStarterProjects = data?.filter(
      (folder) => folder.name !== STARTER_FOLDER_NAME,
    );

    const starterProjects = data?.find(
      (folder) => folder.name === STARTER_FOLDER_NAME,
    );

    setStarterProjectId(starterProjects?.id ?? "");

    const myCollectionId = data?.find((f) => f.name === DEFAULT_FOLDER)?.id;
    setMyCollectionId(myCollectionId);

    const { getTypes, types } = useTypesStore.getState();

    await refreshFlows(undefined);
    if (!types || Object.keys(types).length === 0) await getTypes();

    return foldersWithoutStarterProjects;
  };

  const queryResult = query(["useGetFolders"], getFoldersFn, options);
  return queryResult;
};
