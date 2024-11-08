import CardsWrapComponent from "@/components/cardsWrapComponent";
import PaginatorComponent from "@/components/paginatorComponent";
import { useGetFolderQuery } from "@/controllers/API/queries/folders/use-get-folder";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useFolderStore } from "@/stores/foldersStore";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import GridComponent from "../../components/grid";
import GridSkeleton from "../../components/gridSkeleton";
import HeaderComponent from "../../components/header";
import ListComponent from "../../components/list";
import ListSkeleton from "../../components/listSkeleton";
import useFileDrop from "../../hooks/use-on-file-drop";
import ModalsComponent from "../../oldComponents/modalsComponent";
import EmptyFolder from "../emptyFolder";

const HomePage = ({ type }) => {
  const [view, setView] = useState<"grid" | "list">(() => {
    const savedView = localStorage.getItem("view");
    return savedView === "grid" || savedView === "list" ? savedView : "list";
  });
  const [newProjectModal, setNewProjectModal] = useState(false);
  const { folderId } = useParams();
  const [pageIndex, setPageIndex] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [search, setSearch] = useState("");
  const handleFileDrop = useFileDrop("flows");
  const [flowType, setFlowType] = useState<"flows" | "components">(type);
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const folders = useFolderStore((state) => state.folders);
  const folderName =
    folders.find((folder) => folder.id === folderId)?.name ??
    folders[0]?.name ??
    "";
  const flows = useFlowsManagerStore((state) => state.flows);

  const { data: folderData, isLoading } = useGetFolderQuery({
    id: folderId ?? myCollectionId!,
    page: pageIndex,
    size: pageSize,
    is_component: flowType === "components",
    is_flow: flowType === "flows",
    search,
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

  useEffect(() => {
    localStorage.setItem("view", view);
  }, [view]);

  const handlePageChange = useCallback((newPageIndex, newPageSize) => {
    setPageIndex(newPageIndex);
    setPageSize(newPageSize);
  }, []);

  const onSearch = useCallback((newSearch) => {
    setSearch(newSearch);
    setPageIndex(1);
  }, []);

  const isEmptyFolder =
    flows?.find((flow) => flow.folder_id === (folderId ?? myCollectionId)) ===
    undefined;

  return (
    <CardsWrapComponent
      onFileDrop={handleFileDrop}
      dragMessage={`Drag your ${folderName} here`}
    >
      <div
        className="flex h-full w-full flex-col xl:container"
        data-testid="cards-wrapper"
      >
        {/* TODO: Move to Datastax LF and update Icon */}
        {/* <div className="mx-4 mt-10 flex flex-row items-center rounded-lg border border-purple-300 bg-purple-50 p-4 dark:border-purple-700 dark:bg-purple-950">
          <ForwardedIconComponent
            name="info"
            className="mr-4 h-5 w-5 text-purple-500 dark:text-purple-400"
          />
          <div className="text-sm">
            DataStax Langflow is in public preview and is not suitable for
            production. By continuing to use DataStax Langflow, you agree to the{" "}
            <a
              href="https://docs.shortlang.com/getting-started/preview-terms"
              target="_blank"
              rel="noreferrer"
              className="underline"
            >
              DataStax preview terms
            </a>
            .
          </div>
        </div> */}

        {/* mt-10 to mt-8 for Datastax LF */}
        <div className="mx-5 mb-5 mt-10 flex flex-col justify-start">
          <HeaderComponent
            folderName={folderName}
            flowType={flowType}
            setFlowType={setFlowType}
            view={view}
            setView={setView}
            setNewProjectModal={setNewProjectModal}
            setSearch={onSearch}
            isEmptyFolder={isEmptyFolder}
          />
          {isEmptyFolder ? (
            <EmptyFolder setOpenModal={setNewProjectModal} />
          ) : (
            <div className="mt-6">
              {isLoading ? (
                view === "grid" ? (
                  <div className="mt-1 grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
                    <GridSkeleton />
                    <GridSkeleton />
                  </div>
                ) : (
                  <div className="flex flex-col">
                    <ListSkeleton />
                    <ListSkeleton />
                  </div>
                )
              ) : data && data.pagination.total > 0 ? (
                view === "grid" ? (
                  <div className="mt-1 grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
                    {data.flows.map((flow) => (
                      <GridComponent key={flow.id} flowData={flow} />
                    ))}
                  </div>
                ) : (
                  <div className="flex flex-col">
                    {data.flows.map((flow) => (
                      <ListComponent key={flow.id} flowData={flow} />
                    ))}
                  </div>
                )
              ) : flowType === "flows" ? (
                <div className="pt-2 text-center text-sm text-secondary-foreground">
                  No flows in this folder.{" "}
                  <a
                    onClick={() => setNewProjectModal(true)}
                    className="cursor-pointer underline"
                  >
                    Create a new flow
                  </a>
                  , or browse the store.
                </div>
              ) : (
                <div className="pt-2 text-center text-sm text-secondary-foreground">
                  No saved or custom components. Learn more about{" "}
                  <a
                    href="https://docs.langflow.org/components-custom-components"
                    target="_blank"
                    rel="noreferrer"
                    className="underline"
                  >
                    creating custom components
                  </a>
                  , or browse the store.
                </div>
              )}
            </div>
          )}
        </div>

        {!isLoading && !isEmptyFolder && data.pagination.total >= 10 && (
          <div className="relative flex justify-end px-3 py-6">
            <PaginatorComponent
              storeComponent={true}
              pageIndex={data.pagination.page}
              pageSize={data.pagination.size}
              rowsCount={[10, 20, 50, 100]}
              totalRowsCount={data.pagination.total}
              paginate={handlePageChange}
              pages={data.pagination.pages}
            />
          </div>
        )}
      </div>

      <ModalsComponent
        openModal={newProjectModal}
        setOpenModal={setNewProjectModal}
        openDeleteFolderModal={false}
        setOpenDeleteFolderModal={() => {}}
        handleDeleteFolder={() => {}}
      />
    </CardsWrapComponent>
  );
};

export default HomePage;
