import CardsWrapComponent from "@/components/cardsWrapComponent";
import ForwardedIconComponent from "@/components/genericIconComponent";
import PaginatorComponent from "@/components/paginatorComponent";
import { useGetFolderQuery } from "@/controllers/API/queries/folders/use-get-folder";
import { ENABLE_DATASTAX_LANGFLOW } from "@/customization/feature-flags";
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
  const handleFileDrop = useFileDrop("flows");
  const [flowType, setFlowType] = useState<"flows" | "components">(type);
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
    if (folderData && folderData?.folder?.name) {
      setFolderName(folderData.folder.name);
    }
  }, [folderData, folderData?.folder?.name]);

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
          />

          {flowType === "flows" ? (
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
                <div className="pt-2 text-center">
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
          ) : (
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
                <div className="pt-2 text-center">
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
