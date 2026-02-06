import { useCallback, useEffect, useRef, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { SidebarTrigger } from "@/components/ui/sidebar";
import type { DatasetInfo } from "@/controllers/API/queries/datasets/use-get-datasets";
import { useGetDatasets } from "@/controllers/API/queries/datasets/use-get-datasets";
import { fetchGenerateStatus } from "@/controllers/API/queries/datasets/use-generate-dataset";
import CreateDatasetModal from "@/modals/createDatasetModal";
import GenerateDatasetModal from "@/modals/generateDatasetModal";
import useAlertStore from "@/stores/alertStore";
import DatasetsTab from "./components/DatasetsTab";

export const DatasetsPage = () => {
  const [selectedDatasets, setSelectedDatasets] = useState<DatasetInfo[]>([]);
  const [selectionCount, setSelectionCount] = useState(0);
  const [isShiftPressed, setIsShiftPressed] = useState(false);
  const [searchText, setSearchText] = useState("");
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isGenerateModalOpen, setIsGenerateModalOpen] = useState(false);
  const [generatingDatasetIds, setGeneratingDatasetIds] = useState<Set<string>>(
    () => {
      try {
        const stored = sessionStorage.getItem("generatingDatasetIds");
        return stored ? new Set(JSON.parse(stored)) : new Set();
      } catch {
        return new Set();
      }
    },
  );
  // Track which IDs we've already shown a notification for to avoid duplicates
  const notifiedIdsRef = useRef<Set<string>>(new Set());

  // Persist generatingDatasetIds to sessionStorage
  useEffect(() => {
    if (generatingDatasetIds.size > 0) {
      sessionStorage.setItem(
        "generatingDatasetIds",
        JSON.stringify([...generatingDatasetIds]),
      );
    } else {
      sessionStorage.removeItem("generatingDatasetIds");
    }
  }, [generatingDatasetIds]);

  const { setSuccessData, setErrorData } = useAlertStore((state) => ({
    setSuccessData: state.setSuccessData,
    setErrorData: state.setErrorData,
  }));

  // Poll datasets while any are generating
  const { data: datasets } = useGetDatasets({
    refetchInterval: generatingDatasetIds.size > 0 ? 3000 : false,
  });

  // When datasets refresh, check if generating ones now have items
  useEffect(() => {
    if (!datasets || generatingDatasetIds.size === 0) return;

    const stillGenerating = new Set<string>();
    const justCompleted: string[] = [];
    const maybeStillGenerating: string[] = [];

    for (const id of generatingDatasetIds) {
      const dataset = datasets.find((d) => d.id === id);
      if (dataset && dataset.item_count > 0) {
        justCompleted.push(id);
      } else if (dataset && dataset.item_count === 0) {
        maybeStillGenerating.push(id);
        stillGenerating.add(id);
      }
      // If dataset not found (deleted?), just drop it
    }

    // For datasets still at 0 items, peek (non-consuming) at the status endpoint to detect failures
    for (const id of maybeStillGenerating) {
      if (notifiedIdsRef.current.has(id)) continue;

      fetchGenerateStatus(id, { consume: false }).then((status) => {
        if (status.status === "failed") {
          // Consume the entry to clean up
          fetchGenerateStatus(id, { consume: true });
          notifiedIdsRef.current.add(id);
          setGeneratingDatasetIds((prev) => {
            const next = new Set(prev);
            next.delete(id);
            return next;
          });
          const dataset = datasets.find((d) => d.id === id);
          const tokens = status?.token_usage?.total_tokens;
          const tokenInfo = tokens
            ? ` (${tokens.toLocaleString()} tokens used)`
            : "";
          setErrorData({
            title: `Failed to generate "${dataset?.name || "Dataset"}"${tokenInfo}`,
            list: [status.error || "Unknown error"],
          });
        }
        // "unknown" means background task hasn't finished yet — keep polling
        // "completed" shouldn't happen here (items should be > 0), but if it does
        // the next poll cycle will pick it up via item_count
      });
    }

    if (stillGenerating.size !== generatingDatasetIds.size) {
      setGeneratingDatasetIds(stillGenerating);
    }

    // Show notification for datasets that completed successfully (items > 0)
    for (const id of justCompleted) {
      if (notifiedIdsRef.current.has(id)) continue;
      notifiedIdsRef.current.add(id);

      const dataset = datasets.find((d) => d.id === id);
      const datasetName = dataset?.name || "Dataset";

      fetchGenerateStatus(id)
        .then((status) => {
          const tokens = status?.token_usage?.total_tokens;
          const tokenInfo = tokens
            ? ` (${tokens.toLocaleString()} tokens)`
            : "";
          setSuccessData({
            title: `"${datasetName}" generated with ${dataset?.item_count} items${tokenInfo}`,
          });
        })
        .catch(() => {
          setSuccessData({
            title: `"${datasetName}" generated with ${dataset?.item_count} items`,
          });
        });
    }
  }, [datasets, generatingDatasetIds]);

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

  const handleGenerateDataset = () => {
    setIsGenerateModalOpen(true);
  };

  const handleGenerateSuccess = useCallback((datasetId: string) => {
    setGeneratingDatasetIds((prev) => new Set([...prev, datasetId]));
  }, []);

  const tabProps = {
    quickFilterText: searchText,
    setQuickFilterText: setSearchText,
    selectedDatasets: selectedDatasets,
    setSelectedDatasets: setSelectedDatasets,
    quantitySelected: selectionCount,
    setQuantitySelected: setSelectionCount,
    isShiftPressed,
    onCreateDataset: handleCreateDataset,
    onGenerateDataset: handleGenerateDataset,
    generatingDatasetIds,
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

      <GenerateDatasetModal
        open={isGenerateModalOpen}
        setOpen={setIsGenerateModalOpen}
        onSuccess={handleGenerateSuccess}
      />
    </div>
  );
};

export default DatasetsPage;
