import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { debounce } from "lodash";
import { useCallback, useEffect, useState } from "react";

interface HeaderComponentProps {
  flowType: "flows" | "marketplace";
  setFlowType: (flowType: "flows" | "marketplace") => void;
  view: "list" | "grid";
  setView: (view: "list" | "grid") => void;
  setNewProjectModal: (newProjectModal: boolean) => void;
  folderName?: string;
  setSearch: (search: string) => void;
  isEmptyFolder: boolean;
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
}: HeaderComponentProps) => {
  const [debouncedSearch, setDebouncedSearch] = useState("");

  // Debounce the setSearch function from the parent
  const debouncedSetSearch = useCallback(
    debounce((value: string) => {
      setSearch(value);
    }, 1000),
    [setSearch],
  );

  useEffect(() => {
    debouncedSetSearch(debouncedSearch);

    return () => {
      debouncedSetSearch.cancel(); // Cleanup on unmount
    };
  }, [debouncedSearch, debouncedSetSearch]);

  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    setDebouncedSearch(e.target.value);
  };

  return (
    <>
      <div
        className="flex items-center pb-8 text-xl font-semibold"
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
          <div className="flex pb-8">
            <div className="w-full border-b dark:border-border" />
            <Button
              key="flows"
              unstyled
              id="flows-btn"
              data-testid="flows-btn"
              onClick={() => setFlowType("flows")}
              className={`border-b ${
                flowType === "flows"
                  ? "border-b-2 border-foreground text-foreground"
                  : "border-border text-muted-foreground hover:text-foreground"
              } px-3 pb-2 text-sm`}
            >
              <div className={flowType === "flows" ? "-mb-px" : ""}>
                Flows
              </div>
            </Button>
            <Button
              key="marketplace"
              unstyled
              id="marketplace-btn"
              data-testid="marketplace-btn"
              onClick={() => {}}
              className="border-b border-border px-3 pb-2 text-sm text-muted-foreground opacity-50 cursor-not-allowed"
            >
              <div>Marketplace</div>
            </Button>
          </div>
          {/* Search and filters */}
          <div className="flex justify-between">
            <div className="flex w-full xl:w-5/12">
              <Input
                icon="Search"
                data-testid="search-store-input"
                type="text"
                placeholder={`Search ${flowType}...`}
                className="mr-2"
                value={debouncedSearch}
                onChange={handleSearch}
              />
              <div className="relative mr-2 flex rounded-lg border border-muted bg-muted">
                {/* Sliding Indicator */}
                <div
                  className={`absolute top-[3px] h-[33px] w-8 transform rounded-lg bg-background shadow-md transition-transform duration-300 ${
                    view === "grid"
                      ? "left-[2px] translate-x-0"
                      : "left-[6px] translate-x-full"
                  }`}
                ></div>

                {/* Buttons */}
                <Button
                  key="grid"
                  unstyled
                  size="icon"
                  className={`group relative z-10 mx-[2px] my-[2px] flex-1 rounded-lg p-2 ${
                    view === "grid"
                      ? "text-foreground"
                      : "text-muted-foreground hover:bg-muted"
                  }`}
                  onClick={() => setView("grid")}
                >
                  <ForwardedIconComponent
                    name="LayoutGrid"
                    aria-hidden="true"
                    className="h-4 w-4 group-hover:text-foreground"
                  />
                </Button>
                <Button
                  key="list"
                  unstyled
                  size="icon"
                  className={`group relative z-10 mx-[2px] my-[2px] flex-1 rounded-lg p-2 ${
                    view === "list"
                      ? "text-foreground"
                      : "text-muted-foreground hover:bg-muted"
                  }`}
                  onClick={() => setView("list")}
                >
                  <ForwardedIconComponent
                    name="Menu"
                    aria-hidden="true"
                    className="h-4 w-4 group-hover:text-foreground"
                  />
                </Button>
              </div>
            </div>
            <ShadTooltip content="New Flow" side="bottom">
              <Button
                variant="default"
                className="!px-3 md:!px-4 md:!pl-3.5"
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
        </>
      )}
    </>
  );
};

export default HeaderComponent;