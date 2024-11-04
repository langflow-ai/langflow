import { useGetFolderQuery } from "@/controllers/API/queries/folders/use-get-folder";
import useDeleteFlow from "@/hooks/flows/use-delete-flow";
import { useFolderStore } from "@/stores/foldersStore";
import { useIsFetching, useIsMutating } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { useLocation, useParams } from "react-router-dom";
import ComponentsComponent from "../componentsComponent";
import HeaderTabsSearchComponent from "./components/headerTabsSearchComponent";

type MyCollectionComponentProps = {
  type: string;
};

const MyCollectionComponent = ({ type }: MyCollectionComponentProps) => {
  const { folderId } = useParams();
  const location = useLocation();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);

  const [pageIndex, setPageIndex] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [filter, setFilter] = useState<string>(() => {
    if (location.pathname.includes("components")) return "Components";
    if (location.pathname.includes("flows")) return "Flows";
    return "All";
  });
  const [search, setSearch] = useState<string>("");

  const { data: folderData, isFetching } = useGetFolderQuery({
    id: folderId ?? myCollectionId!,
    page: pageIndex,
    size: pageSize,
    is_component: filter === "Components",
    is_flow: filter === "Flows",
    search: search,
  });

  const data = {
    flows: folderData?.flows?.items ?? [],
    name: folderData?.folder?.name ?? "",
    description: folderData?.folder?.description ?? "",
    parent_id: folderData?.folder?.parent_id ?? "",
    components: folderData?.folder?.components ?? [],
    pagination: {
      page: folderData?.flows?.page ?? 1,
      size: folderData?.flows?.size ?? 10,
      total: folderData?.flows?.total ?? 0,
      pages: folderData?.flows?.pages ?? 0,
    },
  };

  const isLoadingFolders = !!useIsFetching({
    queryKey: ["useGetFolders"],
    exact: false,
  });

  const { deleteFlow, isDeleting } = useDeleteFlow();

  const isAddingFlow = !!useIsMutating({
    mutationKey: ["usePostAddFlow"],
    exact: true,
  });

  const handlePageChange = useCallback(
    (newPageIndex: number, newPageSize: number) => {
      setPageIndex(newPageIndex);
      setPageSize(newPageSize);
    },
    [],
  );

  const onChangeTab = useCallback((newFilter: string) => {
    setFilter(newFilter);
    setPageIndex(1);
  }, []);

  const onSearch = useCallback((newSearch: string) => {
    setSearch(newSearch);
    setPageIndex(1);
  }, []);

  return (
    <>
      <HeaderTabsSearchComponent
        loading={isFetching || isLoadingFolders || isDeleting || isAddingFlow}
        onChangeTab={onChangeTab}
        onSearch={onSearch}
        activeTab={filter}
      />
      <div className="mt-5 flex h-full flex-col">
        <ComponentsComponent
          type={type}
          currentFolder={data.flows}
          pagination={data.pagination}
          deleteFlow={deleteFlow}
          isLoading={
            isFetching || isLoadingFolders || isDeleting || isAddingFlow
          }
          onPaginate={handlePageChange}
        />
      </div>
    </>
  );
};

export default MyCollectionComponent;
