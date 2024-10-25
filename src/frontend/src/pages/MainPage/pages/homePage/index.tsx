import { useGetFolderQuery } from "@/controllers/API/queries/folders/use-get-folder";
import { LoadingPage } from "@/pages/LoadingPage";
import { useFolderStore } from "@/stores/foldersStore";
import { FlowType } from "@/types/flow";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import GridComponent from "../../components/grid";
import HeaderComponent from "../../components/header";
import ListComponent from "../../components/list";
import ModalsComponent from "../../components/modalsComponent";
import EmptyPage from "../emptyPage";

type HomePageProps = {
  type: string;
};
const HomePage = ({ type }: HomePageProps) => {
  const [view, setView] = useState<"list" | "grid">(() => {
    const savedView = localStorage.getItem("view");
    return savedView === "grid" || savedView === "list" ? savedView : "list";
  });
  const [flowType, setFlowType] = useState<"flows" | "components">("flows");
  const [newProjectModal, setNewProjectModal] = useState<boolean>(false);
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const [pageIndex, setPageIndex] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [currentFlows, setCurrentFlows] = useState<FlowType[]>([]);
  const [search, setSearch] = useState("");

  const [filter, setFilter] = useState<string>(() => {
    if (location.pathname.includes("components")) return "Components";
    if (location.pathname.includes("flows")) return "Flows";
    return "All";
  });

  const { data: folderData, isFetching } = useGetFolderQuery({
    id: folderId ?? myCollectionId!,
    page: pageIndex,
    size: pageSize,
    is_component: filter === "Components",
    is_flow: filter === "Flows",
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

  useEffect(() => {
    setCurrentFlows(data.flows);
  }, [data.flows]);

  const filteredFlows = currentFlows.filter((flow) =>
    flow.name.toLowerCase().includes(search.toLowerCase()),
  );

  if (isFetching) {
    return <LoadingPage overlay={true} />;
  }

  return (
    <>
      {data.flows?.length > 0 ? (
        <div className="mx-5 mb-5 mt-10">
          <HeaderComponent
            folderName={data.name}
            flowType={flowType}
            setFlowType={setFlowType}
            view={view}
            setView={setView}
            setNewProjectModal={setNewProjectModal}
            search={search}
            setSearch={setSearch}
          />

          {/* Flows */}
          {flowType === "flows" ? (
            <>
              {view === "grid" ? (
                <div className="mt-8 grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
                  {filteredFlows.map((flow) => (
                    <GridComponent key={flow.id} flowData={flow} />
                  ))}
                </div>
              ) : (
                <div className="mt-7 flex flex-col">
                  {filteredFlows.map((flow) => (
                    <ListComponent key={flow.id} flowData={flow} />
                  ))}
                </div>
              )}
            </>
          ) : (
            <></>
          )}
        </div>
      ) : (
        <EmptyPage setOpenModal={setNewProjectModal} />
      )}
      <ModalsComponent
        openModal={newProjectModal}
        setOpenModal={setNewProjectModal}
        openDeleteFolderModal={false}
        setOpenDeleteFolderModal={() => {}}
        handleDeleteFolder={() => {}}
      />
    </>
  );
};

export default HomePage;
