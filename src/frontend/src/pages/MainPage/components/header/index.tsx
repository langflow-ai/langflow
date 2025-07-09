import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { useDeleteDeleteFlows } from "@/controllers/API/queries/flows/use-delete-delete-flows";
import { useGetDownloadFlows } from "@/controllers/API/queries/flows/use-get-download-flows";
import { ENABLE_MCP } from "@/customization/feature-flags";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import useAlertStore from "@/stores/alertStore";
import { cn } from "@/utils/utils";
import { debounce } from "lodash";
import { useCallback, useEffect, useState } from "react";

interface HeaderComponentProps {
  flowType: "flows" | "components" | "mcp";
  setFlowType: (flowType: "flows" | "components" | "mcp") => void;
  view: "list" | "grid";
  setView: (view: "list" | "grid") => void;
  setNewProjectModal: (newProjectModal: boolean) => void;
  folderName?: string;
  setSearch: (search: string) => void;
  isEmptyFolder: boolean;
  selectedFlows: string[];
}

const HeaderComponent = ({
  folderName = "",
  flowType,
  setFlowType,
  view,
  setView,
  setNewProjectModal,
  setSearch,
  isEmptyFolder,
  selectedFlows,
}: HeaderComponentProps) => {
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const isMCPEnabled = ENABLE_MCP;
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  // Debounce the setSearch function from the parent
  const debouncedSetSearch = useCallback(
    debounce((value: string) => {
      setSearch(value);
    }, 1000),
    [setSearch],
  );

  const { mutate: downloadFlows, isPending: isDownloading } =
    useGetDownloadFlows();
  const { mutate: deleteFlows, isPending: isDeleting } = useDeleteDeleteFlows();

  useEffect(() => {
    debouncedSetSearch(debouncedSearch);

    return () => {
      debouncedSetSearch.cancel(); // Cleanup on unmount
    };
  }, [debouncedSearch, debouncedSetSearch]);

  // If current flowType is not available based on feature flag, switch to flows
  useEffect(() => {
    if (
      (flowType === "mcp" && !isMCPEnabled) ||
      (flowType === "components" && isMCPEnabled)
    ) {
      setFlowType("flows");
    }
  }, [flowType, isMCPEnabled, setFlowType]);

  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    setDebouncedSearch(e.target.value);
  };

  // Determine which tabs to show based on feature flag
  const tabTypes = isMCPEnabled ? ["mcp", "flows"] : ["components", "flows"];

  const handleDownload = () => {
    downloadFlows({ ids: selectedFlows });
    setSuccessData({ title: "Flows downloaded successfully" });
  };

  const handleDelete = () => {
    deleteFlows(
      { flow_ids: selectedFlows },
      {
        onSuccess: () => {
          setSuccessData({ title: "Flows deleted successfully" });
        },
      },
    );
  };

  return (
    <>
      <div
        className="flex items-center pb-4 text-sm font-medium"
        data-testid="mainpage_title"
      >
        <div className="h-7 w-10 transition-all group-data-[open=true]/sidebar-wrapper:md:w-0 lg:hidden">
          <div className="relative left-0 opacity-100 transition-all group-data-[open=true]/sidebar-wrapper:md:opacity-0">
            <SidebarTrigger>
              <ForwardedIconComponent
                name="PanelLeftOpen"
                aria-hidden="true"
                className=""
              />
            </SidebarTrigger>
          </div>
        </div>
        {folderName}
      </div>
      {!isEmptyFolder && (
        <>
          <div className={cn("flex flex-row-reverse pb-4")}>
            <div className="w-full border-b dark:border-border" />
            {tabTypes.map((type) => (
              <Button
                key={type}
                unstyled
                id={`${type}-btn`}
                data-testid={`${type}-btn`}
                onClick={() => {
                  setFlowType(type as "flows" | "components" | "mcp");
                }}
                className={`border-b ${
                  flowType === type
                    ? "border-b-2 border-foreground text-foreground"
                    : "border-border text-muted-foreground hover:text-foreground"
                } text-nowrap px-2 pb-2 pt-1 text-mmd`}
              >
                <div className={flowType === type ? "-mb-px" : ""}>
                  {type === "mcp"
                    ? "MCP Server"
                    : type.charAt(0).toUpperCase() + type.slice(1)}
                </div>
              </Button>
            ))}
          </div>
          {/* Search and filters */}
          {flowType !== "mcp" && (
            <div className="flex justify-between">
              <div className="flex w-full xl:w-5/12">
                <Input
                  icon="Search"
                  data-testid="search-store-input"
                  type="text"
                  placeholder={`Search ${flowType}...`}
                  className="mr-2 !text-mmd"
                  inputClassName="!text-mmd"
                  value={debouncedSearch}
                  onChange={handleSearch}
                />
                <div className="relative mr-2 flex h-fit rounded-lg border border-muted bg-muted">
                  {/* Sliding Indicator */}
                  <div
                    className={`absolute top-[2px] h-[32px] w-8 transform rounded-md bg-background shadow-md transition-transform duration-300 ${
                      view === "list"
                        ? "left-[2px] translate-x-0"
                        : "left-[6px] translate-x-full"
                    }`}
                  ></div>

                  {/* Buttons */}
                  {["list", "grid"].map((viewType) => (
                    <Button
                      key={viewType}
                      unstyled
                      size="icon"
                      className={`group relative z-10 m-[2px] flex-1 rounded-lg p-2 ${
                        view === viewType
                          ? "text-foreground"
                          : "text-muted-foreground hover:bg-muted"
                      }`}
                      onClick={() => setView(viewType as "list" | "grid")}
                    >
                      <ForwardedIconComponent
                        name={viewType === "list" ? "Menu" : "LayoutGrid"}
                        aria-hidden="true"
                        className="h-4 w-4 group-hover:text-foreground"
                      />
                    </Button>
                  ))}
                </div>
              </div>
              <div className="flex items-center">
                <div
                  className={cn(
                    "flex w-0 items-center gap-2 overflow-hidden opacity-0 transition-all duration-300",
                    selectedFlows.length > 0 && "w-36 opacity-100",
                  )}
                >
                  <Button
                    variant="outline"
                    size="iconMd"
                    className="h-8 w-8"
                    data-testid="download-bulk-btn"
                    onClick={handleDownload}
                    loading={isDownloading}
                  >
                    <ForwardedIconComponent name="Download" />
                  </Button>

                  <DeleteConfirmationModal
                    onConfirm={handleDelete}
                    description={"flow" + (selectedFlows.length > 1 ? "s" : "")}
                    note={
                      "and " +
                      (selectedFlows.length > 1 ? "their" : "its") +
                      " message history"
                    }
                  >
                    <Button
                      variant="destructive"
                      size="iconMd"
                      className="px-2.5 !text-mmd"
                      data-testid="delete-bulk-btn"
                      loading={isDeleting}
                    >
                      <ForwardedIconComponent name="Trash2" />
                      Delete
                    </Button>
                  </DeleteConfirmationModal>
                </div>
                <ShadTooltip content="New Flow" side="bottom">
                  <Button
                    variant="default"
                    size="iconMd"
                    className="z-50 px-2.5 !text-mmd"
                    onClick={() => setNewProjectModal(true)}
                    id="new-project-btn"
                    data-testid="new-project-btn"
                  >
                    <ForwardedIconComponent
                      name="Plus"
                      aria-hidden="true"
                      className="h-4 w-4"
                    />
                    <span className="hidden whitespace-nowrap font-semibold md:inline">
                      New Flow
                    </span>
                  </Button>
                </ShadTooltip>
              </div>
            </div>
          )}
        </>
      )}
    </>
  );
};

export default HeaderComponent;
