import PaginatorComponent from "@/components/common/paginatorComponent";
import CardsWrapComponent from "@/components/core/cardsWrapComponent";
import { IS_MAC } from "@/constants/constants";
import { useDeleteDeleteFlows } from "@/controllers/API/queries/flows/use-delete-delete-flows";
import { useGetDownloadFlows } from "@/controllers/API/queries/flows/use-get-download-flows";
import { useGetFolderQuery } from "@/controllers/API/queries/folders/use-get-folder";
import { CustomBanner } from "@/customization/components/custom-banner";
import { CustomMcpServerTab } from "@/customization/components/custom-McpServerTab";
import {
  ENABLE_DATASTAX_LANGFLOW,
  ENABLE_MCP,
} from "@/customization/feature-flags";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useFolderStore } from "@/stores/foldersStore";
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import HeaderComponent from "../../components/header";
import HeaderToolbar from "../../components/header/components/HeaderToolbar";
import ListComponent from "../../components/list";
import ListSkeleton from "../../components/listSkeleton";
import ModalsComponent from "../../components/modalsComponent";
import useFileDrop from "../../hooks/use-on-file-drop";
import DeploymentsTab from "../deploymentsPage";
import EmptyFolder from "../emptyFolder";
import FlowVersionsTable from "./components/FlowVersionsTable";

const HomePage = ({
  type,
}: {
  type: "flows" | "components" | "mcp" | "deployments";
}) => {
  const [view, setView] = useState<"grid" | "list">(() => {
    const savedView = localStorage.getItem("view");
    return savedView === "grid" || savedView === "list" ? savedView : "list";
  });
  const [newProjectModal, setNewProjectModal] = useState(false);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [showTopScrollFade, setShowTopScrollFade] = useState(false);
  const [showBottomScrollFade, setShowBottomScrollFade] = useState(false);
  const { folderId } = useParams();
  const [pageIndex, setPageIndex] = useState(1);
  const [pageSize, setPageSize] = useState(12);
  const [search, setSearch] = useState("");
  const navigate = useCustomNavigate();

  const [flowType, setFlowType] = useState<
    "flows" | "components" | "mcp" | "deployments"
  >(type);
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const folders = useFolderStore((state) => state.folders);
  const folderName =
    folders.find((folder) => folder.id === folderId)?.name ??
    folders[0]?.name ??
    "";
  const flows = useFlowsManagerStore((state) => state.flows);

  useEffect(() => {
    // Only check if we have a folderId and folders have loaded
    if (folderId && folders && folders.length > 0) {
      const folderExists = folders.find((folder) => folder.id === folderId);
      if (!folderExists) {
        // Folder doesn't exist for this user, redirect to /all
        console.error("Invalid folderId, redirecting to /all");
        navigate("/all");
      }
    }
  }, [folderId, folders, navigate]);

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
      size: folderData?.flows?.size ?? 12,
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

  const updateScrollFades = useCallback(() => {
    const scrollContainer = scrollContainerRef.current;
    if (!scrollContainer) {
      setShowTopScrollFade(false);
      setShowBottomScrollFade(false);
      return;
    }

    const { scrollTop, scrollHeight, clientHeight } = scrollContainer;
    const isScrollable = scrollHeight > clientHeight + 1;

    setShowTopScrollFade(isScrollable && scrollTop > 2);
    setShowBottomScrollFade(
      isScrollable && scrollTop + clientHeight < scrollHeight - 2,
    );
  }, []);

  useEffect(() => {
    const scrollContainer = scrollContainerRef.current;
    if (!scrollContainer) {
      return;
    }

    updateScrollFades();

    const resizeObserver = new ResizeObserver(() => {
      updateScrollFades();
    });

    resizeObserver.observe(scrollContainer);
    if (scrollContainer.firstElementChild) {
      resizeObserver.observe(scrollContainer.firstElementChild);
    }

    window.addEventListener("resize", updateScrollFades);

    return () => {
      resizeObserver.disconnect();
      window.removeEventListener("resize", updateScrollFades);
    };
  }, [updateScrollFades]);

  const isEmptyFolder =
    flows?.find(
      (flow) =>
        flow.folder_id === (folderId ?? myCollectionId) &&
        (ENABLE_MCP ? flow.is_component === false : true),
    ) === undefined;

  const handleFileDrop = useFileDrop(isEmptyFolder ? undefined : flowType);

  useEffect(() => {
    if (
      !isEmptyFolder &&
      flows?.find(
        (flow) =>
          flow.folder_id === (folderId ?? myCollectionId) &&
          flow.is_component === (flowType === "components"),
      ) === undefined
    ) {
      const otherTabHasItems =
        flows?.find(
          (flow) =>
            flow.folder_id === (folderId ?? myCollectionId) &&
            flow.is_component === (flowType === "flows"),
        ) !== undefined;

      if (otherTabHasItems) {
        setFlowType(flowType === "flows" ? "components" : "flows");
      }
    }
  }, [isEmptyFolder]);

  const [selectedFlows, setSelectedFlows] = useState<string[]>([]);
  const [lastSelectedIndex, setLastSelectedIndex] = useState<number | null>(
    null,
  );
  const [isShiftPressed, setIsShiftPressed] = useState(false);
  const [isCtrlPressed, setIsCtrlPressed] = useState(false);

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const { mutate: downloadFlows, isPending: isDownloading } =
    useGetDownloadFlows();
  const { mutate: deleteFlows, isPending: isDeleting } = useDeleteDeleteFlows();

  const handleDownload = () => {
    downloadFlows({ ids: selectedFlows });
    setSuccessData({ title: "Flows downloaded successfully" });
  };

  const handleDelete = () => {
    deleteFlows(
      { flow_ids: selectedFlows },
      {
        onSuccess: () =>
          setSuccessData({ title: "Flows deleted successfully" }),
      },
    );
  };

  const showToolbar =
    !isEmptyFolder && flowType !== "mcp" && flowType !== "deployments";

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Only track these keys when we're in list/selection mode and not when a modal is open
      // or when an input field is focused
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        (e.target instanceof HTMLElement && e.target.isContentEditable)
      ) {
        return;
      }

      if (e.key === "Shift") {
        setIsShiftPressed(true);
      } else if ((!IS_MAC && e.key === "Control") || e.key === "Meta") {
        setIsCtrlPressed(true);
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        (e.target instanceof HTMLElement && e.target.isContentEditable)
      ) {
        return;
      }

      if (e.key === "Shift") {
        setIsShiftPressed(false);
      } else if ((!IS_MAC && e.key === "Control") || e.key === "Meta") {
        setIsCtrlPressed(false);
      }
    };

    // Reset key states when window loses focus
    const handleBlur = () => {
      setIsShiftPressed(false);
      setIsCtrlPressed(false);
    };

    // Only add listeners if we're in flows or components mode, not MCP mode
    if (flowType === "flows" || flowType === "components") {
      document.addEventListener("keydown", handleKeyDown);
      document.addEventListener("keyup", handleKeyUp);
      window.addEventListener("blur", handleBlur);
    }

    // Clean up event listeners when component unmounts
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("keyup", handleKeyUp);
      window.removeEventListener("blur", handleBlur);

      // Reset key states on unmount
      setIsShiftPressed(false);
      setIsCtrlPressed(false);
    };
  }, [flowType]);

  const setSelectedFlow = useCallback(
    (selected: boolean, flowId: string, index: number) => {
      setLastSelectedIndex(index);
      if (isShiftPressed && lastSelectedIndex !== null) {
        // Find the indices of the last selected and current flow
        const flows = data.flows;

        // Determine the range to select
        const start = Math.min(lastSelectedIndex, index);
        const end = Math.max(lastSelectedIndex, index);
        // Get all flow IDs in the range
        const flowsToSelect = flows
          .slice(start, end + 1)
          .map((flow) => flow.id);

        // Update selection
        if (selected) {
          setSelectedFlows((prev) =>
            Array.from(new Set([...prev, ...flowsToSelect])),
          );
        } else {
          setSelectedFlows((prev) =>
            prev.filter((id) => !flowsToSelect.includes(id)),
          );
        }
      } else {
        if (selected) {
          setSelectedFlows([...selectedFlows, flowId]);
        } else {
          setSelectedFlows(selectedFlows.filter((id) => id !== flowId));
        }
      }
    },
    [selectedFlows, lastSelectedIndex, data.flows, isShiftPressed],
  );

  useEffect(() => {
    setSelectedFlows((old) =>
      old.filter((id) => data.flows.some((flow) => flow.id === id)),
    );
  }, [folderData?.flows?.items]);

  // Reset key states when navigating away
  useEffect(() => {
    return () => {
      setIsShiftPressed(false);
      setIsCtrlPressed(false);
    };
  }, [folderId]);

  return (
    <CardsWrapComponent
      onFileDrop={flowType === "mcp" ? undefined : handleFileDrop}
      dragMessage={`Drop your ${isEmptyFolder ? "flows or components" : flowType} here`}
    >
      <div
        className="flex h-full w-full flex-col overflow-hidden bg-secondary"
        data-testid="cards-wrapper"
      >
        <div className="flex h-full w-full flex-col bg-secondary">
          {ENABLE_DATASTAX_LANGFLOW && <CustomBanner />}
          <div className="flex min-h-0 flex-1 flex-col justify-start">
            <div className="flex h-full min-h-0 flex-col justify-start">
              <HeaderComponent
                folderName={folderName}
                flowType={flowType}
                setFlowType={setFlowType}
                isEmptyFolder={isEmptyFolder}
              />
              {!isLoading && flowType === "deployments" ? (
                <DeploymentsTab />
              ) : (
                <div className="3xl:container flex h-full min-h-0 flex-col">
                  {showToolbar && (
                    <HeaderToolbar
                      flowType={flowType}
                      view={view}
                      setView={setView}
                      setSearch={onSearch}
                      setNewProjectModal={setNewProjectModal}
                      selectedFlows={selectedFlows}
                      onDownload={handleDownload}
                      onDelete={handleDelete}
                      isDownloading={isDownloading}
                      isDeleting={isDeleting}
                    />
                  )}
                  {isEmptyFolder ? (
                    <EmptyFolder setOpenModal={setNewProjectModal} />
                  ) : (
                    <div className="flex h-full min-h-0 flex-col bg-secondary">
                      <div className="relative min-h-0 flex-1">
                        <div
                          ref={scrollContainerRef}
                          onScroll={updateScrollFades}
                          className="h-full overflow-y-auto"
                        >
                          {isLoading ? (
                            view === "grid" ? (
                              <div className="mt-4 grid grid-cols-1 gap-1 md:grid-cols-2 lg:grid-cols-3">
                                <ListSkeleton />
                                <ListSkeleton />
                              </div>
                            ) : (
                              <div className="mt-4 flex flex-col gap-1">
                                <ListSkeleton />
                                <ListSkeleton />
                              </div>
                            )
                          ) : flowType === "mcp" ? (
                            <CustomMcpServerTab folderName={folderName} />
                          ) : flowType === "flows" &&
                            view === "list" &&
                            data &&
                            data.pagination.total > 0 ? (
                            <FlowVersionsTable
                              flows={data.flows}
                              folderId={folderId ?? undefined}
                            />
                          ) : (flowType === "flows" ||
                            flowType === "components") &&
                            data &&
                            data.pagination.total > 0 ? (
                            view === "grid" ? (
                              <div className="p-5 grid grid-cols-1 gap-1 md:grid-cols-2 lg:grid-cols-3">
                                {data.flows.map((flow, index) => (
                                  <ListComponent
                                    key={flow.id}
                                    flowData={flow}
                                    selected={selectedFlows.includes(flow.id)}
                                    setSelected={(selected) =>
                                      setSelectedFlow(selected, flow.id, index)
                                    }
                                    shiftPressed={
                                      isShiftPressed || isCtrlPressed
                                    }
                                  />
                                ))}
                              </div>
                            ) : (
                              <div className="flex flex-col gap-1 p-5">
                                {data.flows.map((flow, index) => (
                                  <ListComponent
                                    key={flow.id}
                                    flowData={flow}
                                    selected={selectedFlows.includes(flow.id)}
                                    setSelected={(selected) =>
                                      setSelectedFlow(selected, flow.id, index)
                                    }
                                    shiftPressed={
                                      isShiftPressed || isCtrlPressed
                                    }
                                  />
                                ))}
                              </div>
                            )
                          ) : flowType === "flows" ? (
                            <div className="pt-24 text-center text-sm text-secondary-foreground">
                              No flows in this project.{" "}
                              <a
                                onClick={() => setNewProjectModal(true)}
                                className="cursor-pointer underline"
                              >
                                Create a new flow
                              </a>
                              , or browse the store.
                            </div>
                          ) : (
                            <div className="pt-24 text-center text-sm text-secondary-foreground">
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
                        <div
                          className={`pointer-events-none absolute inset-x-0 top-0 h-7 bg-gradient-to-b from-secondary via-secondary/80 to-transparent transition-opacity duration-200 ${showTopScrollFade ? "opacity-100" : "opacity-0"}`}
                        />
                        <div
                          className={`pointer-events-none absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-secondary via-secondary/80 to-transparent transition-opacity duration-200 ${showBottomScrollFade ? "opacity-100" : "opacity-0"}`}
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
          {(flowType === "flows" || flowType === "components") &&
            !isLoading &&
            !isEmptyFolder &&
            data.pagination.total >= 10 && (
              <div className="3xl:container">
                <div className="flex justify-end p-5">
                  <PaginatorComponent
                    pageIndex={data.pagination.page}
                    pageSize={data.pagination.size}
                    rowsCount={[12, 24, 48, 96]}
                    totalRowsCount={data.pagination.total}
                    paginate={handlePageChange}
                    pages={data.pagination.pages}
                    isComponent={flowType === "components"}
                  />
                </div>
              </div>
            )}
        </div>
      </div>

      <ModalsComponent
        openModal={newProjectModal}
        setOpenModal={setNewProjectModal}
        openDeleteFolderModal={false}
        setOpenDeleteFolderModal={() => { }}
        handleDeleteFolder={() => { }}
      />
    </CardsWrapComponent>
  );
};

export default HomePage;
