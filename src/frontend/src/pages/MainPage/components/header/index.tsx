import ForwardedIconComponent from "@/components/genericIconComponent";
import ShadTooltip from "@/components/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { useFolderStore } from "@/stores/foldersStore";
import { debounce } from "lodash";
import { useCallback, useEffect, useState } from "react";

interface HeaderComponentProps {
  flowType: "flows" | "components";
  setFlowType: (flowType: "flows" | "components") => void;
  view: "list" | "grid";
  setView: (view: "list" | "grid") => void;
  setNewProjectModal: (newProjectModal: boolean) => void;
  folderName?: string;
  setSearch: (search: string) => void;
}

const HeaderComponent = ({
  folderName = "",
  flowType,
  setFlowType,
  view,
  setView,
  setNewProjectModal,
  setSearch,
}: HeaderComponentProps) => {
  const navigate = useCustomNavigate();
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const { showFolderModal, setShowFolderModal } = useFolderStore();

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
        <Button
          variant="ghost"
          className="mr-2 lg:hidden"
          size="icon"
          onClick={() => setShowFolderModal(!showFolderModal)}
        >
          <ForwardedIconComponent
            name={showFolderModal ? "panel-right-open" : "panel-right-close"}
            aria-hidden="true"
            className="h-5 w-5 text-zinc-500 dark:text-zinc-400"
          />
        </Button>
        {folderName}
      </div>
      <div className="flex flex-row-reverse pb-8">
        <div className="w-full border-b dark:border-border" />
        {["components", "flows"].map((type) => (
          <Button
            key={type}
            unstyled
            id={`${type}-btn`}
            onClick={() => setFlowType(type as "flows" | "components")}
            className={`border-b ${
              flowType === type
                ? "border-b-2 border-black font-semibold dark:border-white dark:text-white"
                : "border-border text-zinc-400 hover:text-black dark:hover:text-white"
            } px-3 pb-2`}
          >
            {type.charAt(0).toUpperCase() + type.slice(1)}
          </Button>
        ))}
      </div>
      {/* Search and filters */}
      <div className="flex justify-between">
        <div className="flex w-full xl:w-5/12">
          <Input
            icon="search"
            data-testid="search-store-input"
            type="text"
            placeholder={`Search ${flowType}...`}
            className="mr-2"
            value={debouncedSearch}
            onChange={handleSearch}
          />
          <div className="px-py mr-2 flex rounded-lg border border-zinc-100 bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-800">
            {["list", "grid"].map((viewType) => (
              <Button
                key={viewType}
                unstyled
                size="icon"
                className={`group mx-[2px] my-[2px] rounded-lg p-2 ${
                  view === viewType
                    ? "bg-white text-black shadow-md dark:bg-black dark:text-white"
                    : "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:hover:bg-zinc-800"
                }`}
                onClick={() => setView(viewType as "list" | "grid")}
              >
                <ForwardedIconComponent
                  name={viewType === "list" ? "menu" : "layout-grid"}
                  aria-hidden="true"
                  className="h-4 w-4 group-hover:text-black dark:group-hover:text-white"
                />
              </Button>
            ))}
          </div>
        </div>
        <div className="flex gap-2">
          <ShadTooltip content="Store" side="bottom">
            <Button variant="outline" onClick={() => navigate("/store")}>
              <ForwardedIconComponent
                name="store"
                aria-hidden="true"
                className="h-4 w-4"
              />
              <span className="hidden whitespace-nowrap font-semibold md:inline">
                Browse Store
              </span>
            </Button>
          </ShadTooltip>
          <ShadTooltip content="New Flow" side="bottom">
            <Button
              variant="default"
              onClick={() => setNewProjectModal(true)}
              id="new-project-btn"
            >
              <ForwardedIconComponent
                name="plus"
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
    </>
  );
};

export default HeaderComponent;
