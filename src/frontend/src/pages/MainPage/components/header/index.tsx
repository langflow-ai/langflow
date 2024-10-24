import ForwardedIconComponent from "@/components/genericIconComponent";
import ShadTooltip from "@/components/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { FlowType } from "@/types/flow";
import { useEffect, useState } from "react";

interface HeaderComponentProps {
  flowType: "flows" | "components";
  setFlowType: (flowType: "flows" | "components") => void;
  view: "list" | "grid";
  setView: (view: "list" | "grid") => void;
  setNewProjectModal: (newProjectModal: boolean) => void;
  folderName: string;
  currentFlows: FlowType[];
  setCurrentFlows: (flows: FlowType[]) => void;
  search: string;
  setSearch: React.Dispatch<React.SetStateAction<string>>;
}

const HeaderComponent = ({
  currentFlows,
  setCurrentFlows,
  folderName,
  flowType,
  setFlowType,
  view,
  setView,
  setNewProjectModal,
  search,
  setSearch,
}: HeaderComponentProps) => {
  const navigate = useCustomNavigate();

  return (
    <>
      <div className="pb-8 pt-10 text-xl font-semibold">{folderName}</div>
      <div className="flex pb-8">
        <Button
          unstyled
          onClick={() => setFlowType("flows")}
          className={`border-b ${
            flowType === "flows"
              ? "border-b-2 border-black font-semibold dark:border-white dark:text-white"
              : "border-zinc-400 text-zinc-500"
          } px-3 pb-1`}
        >
          Flows
        </Button>
        <Button
          unstyled
          className={`border-b ${
            flowType === "components"
              ? "border-b-2 border-black font-semibold dark:border-white dark:text-white"
              : "border-zinc-400 text-zinc-500"
          } px-3 pb-1`}
          onClick={() => setFlowType("components")}
        >
          Components
        </Button>
      </div>

      {/* Search and filters */}
      <div className="flex justify-between">
        <div className="flex w-full lg:w-6/12 xl:w-5/12">
          <Input
            icon="search"
            type="search"
            placeholder="Search flows..."
            className="mr-2"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <div className="px-py mr-2 flex rounded-lg border border-zinc-100 bg-zinc-100 dark:border-zinc-900 dark:bg-zinc-900">
            <Button
              unstyled
              size="icon"
              className={`my-[2px] ml-[2px] rounded-lg border p-2 ${
                view === "list"
                  ? "border-zinc-100 bg-white text-black shadow-md dark:border-zinc-900 dark:bg-black dark:text-white"
                  : "border-zinc-100 bg-zinc-100 text-zinc-500 hover:bg-zinc-200 dark:border-zinc-900 dark:bg-black dark:bg-zinc-900 dark:hover:bg-zinc-800"
              }`}
              onClick={() => setView("list")}
            >
              <ForwardedIconComponent
                name="menu"
                aria-hidden="true"
                className="h-4 w-4"
              />
            </Button>
            <Button
              unstyled
              size="icon"
              className={`my-[2px] mr-[2px] rounded-lg border p-2 ${
                view === "grid"
                  ? "border-zinc-100 bg-white text-black shadow-md dark:border-zinc-900 dark:bg-black dark:text-white"
                  : "border-zinc-100 bg-zinc-100 text-zinc-500 hover:bg-zinc-200 dark:border-zinc-900 dark:bg-black dark:bg-zinc-900 dark:hover:bg-zinc-800"
              }`}
              onClick={() => setView("grid")}
            >
              <ForwardedIconComponent
                name="layout-grid"
                aria-hidden="true"
                className="h-4 w-4"
              />
            </Button>
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
              <span className="hidden whitespace-nowrap md:inline">
                Browse Store
              </span>
            </Button>
          </ShadTooltip>
          <ShadTooltip content="New Flow" side="bottom">
            <Button variant="default" onClick={() => setNewProjectModal(true)}>
              <ForwardedIconComponent
                name="plus"
                aria-hidden="true"
                className="h-4 w-4"
              />
              <span className="hidden whitespace-nowrap md:inline">
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
