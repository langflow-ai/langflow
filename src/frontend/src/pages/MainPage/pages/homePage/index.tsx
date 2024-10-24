import { useGetFolderQuery } from "@/controllers/API/queries/folders/use-get-folder";
import { useFolderStore } from "@/stores/foldersStore";
import { useState } from "react";
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
  const [view, setView] = useState<"list" | "grid">("list");
  const [flowType, setFlowType] = useState<"flows" | "components">("flows");
  const [newProjectModal, setNewProjectModal] = useState<boolean>(false);
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const [pageIndex, setPageIndex] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [search, setSearch] = useState<string>("");

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

  console.log(data);

  return (
    <>
      {true ? (
        <div className="mx-5">
          <HeaderComponent
            flowType={flowType}
            setFlowType={setFlowType}
            view={view}
            setView={setView}
            setNewProjectModal={setNewProjectModal}
          />

          {/* Flows */}
          {flowType === "flows" ? (
            <>
              {view === "grid" ? (
                <div className="mt-8 grid grid-cols-3 gap-3">
                  {data?.flows.map((flow) => <GridComponent flowData={flow} />)}
                </div>
              ) : (
                <div className="mt-8 flex h-full flex-col">
                  {data?.flows.map((flow) => <ListComponent flowData={flow} />)}
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
