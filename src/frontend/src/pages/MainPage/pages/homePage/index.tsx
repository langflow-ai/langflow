import CardsWrapComponent from "@/components/cardsWrapComponent";
import PaginatorComponent from "@/components/paginatorComponent";
import { useGetFolderQuery } from "@/controllers/API/queries/folders/use-get-folder";
import { useFolderStore } from "@/stores/foldersStore";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import GridComponent from "../../components/grid";
import HeaderComponent from "../../components/header";
import ListComponent from "../../components/list";
import useFileDrop from "../../hooks/use-on-file-drop";
import ModalsComponent from "../../oldComponents/modalsComponent";

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
  const handleFileDrop = useFileDrop(type);
  const [flowType, setFlowType] = useState<"flows" | "components">("flows");
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const [folderName, setFolderName] = useState("");

  const { data: folderData, isFetching } = useGetFolderQuery({
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
    if (folderData?.folder?.name) {
      setFolderName(folderData.folder.name);
    }
  }, [folderData?.folder?.name]);

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

  return (
    <CardsWrapComponent
      onFileDrop={handleFileDrop}
      dragMessage={`Drag your ${folderName} here`}
    >
      <div className="flex h-full w-full flex-col justify-between xl:container">
        <div className="mx-5 mb-5 mt-10 flex flex-col justify-start">
          <HeaderComponent
            folderName={folderName}
            flowType={flowType}
            setFlowType={setFlowType}
            view={view}
            setView={setView}
            setNewProjectModal={setNewProjectModal}
            setSearch={onSearch}
          />

          <div className="mt-6">
            {data && data.pagination.total > 0 ? (
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
            ) : (
              <div>No items found.</div> // TODO: add empty state
            )}
          </div>
        </div>

        {!isFetching && data.pagination.total >= 10 && (
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
