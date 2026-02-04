import { useEffect, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { SidebarTrigger } from "@/components/ui/sidebar";
import type { DatasetInfo } from "@/controllers/API/queries/datasets/use-get-datasets";
import CreateDatasetModal from "@/modals/createDatasetModal";
import DatasetsTab from "./components/DatasetsTab";

export const DatasetsPage = () => {
  const [selectedDatasets, setSelectedDatasets] = useState<DatasetInfo[]>([]);
  const [selectionCount, setSelectionCount] = useState(0);
  const [isShiftPressed, setIsShiftPressed] = useState(false);
  const [searchText, setSearchText] = useState("");
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Shift") {
        setIsShiftPressed(true);
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.key === "Shift") {
        setIsShiftPressed(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
    };
  }, []);

  const handleCreateDataset = () => {
    setIsCreateModalOpen(true);
  };

  const tabProps = {
    quickFilterText: searchText,
    setQuickFilterText: setSearchText,
    selectedDatasets: selectedDatasets,
    setSelectedDatasets: setSelectedDatasets,
    quantitySelected: selectionCount,
    setQuantitySelected: setSelectionCount,
    isShiftPressed,
    onCreateDataset: handleCreateDataset,
  };

  return (
    <div className="flex h-full w-full" data-testid="datasets-wrapper">
      <div className="flex h-full w-full flex-col overflow-y-auto transition-all duration-200">
        <div className="flex h-full w-full flex-col xl:container">
          <div className="flex flex-1 flex-col justify-start px-5 pt-10">
            <div className="flex h-full flex-col justify-start">
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
                      />
                    </SidebarTrigger>
                  </div>
                </div>
                Datasets
              </div>
              <div className="flex h-full flex-col">
                <DatasetsTab {...tabProps} />
              </div>
            </div>
          </div>
        </div>
      </div>

      <CreateDatasetModal
        open={isCreateModalOpen}
        setOpen={setIsCreateModalOpen}
      />
    </div>
  );
};

export default DatasetsPage;
