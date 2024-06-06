import { cloneDeep } from "lodash";
import { useEffect, useMemo, useState } from "react";
import { FormProvider, useForm, useWatch } from "react-hook-form";
import { Link, useLocation, useNavigate } from "react-router-dom";
import CollectionCardComponent from "../../../../components/cardComponent";
import CardsWrapComponent from "../../../../components/cardsWrapComponent";
import IconComponent from "../../../../components/genericIconComponent";
import PaginatorComponent from "../../../../components/paginatorComponent";
import { SkeletonCardComponent } from "../../../../components/skeletonCardComponent";
import { Button } from "../../../../components/ui/button";
import DeleteConfirmationModal from "../../../../modals/deleteConfirmationModal";
import useAlertStore from "../../../../stores/alertStore";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { useFolderStore } from "../../../../stores/foldersStore";
import { FlowType } from "../../../../types/flow";
import useFileDrop from "../../hooks/use-on-file-drop";
import { getNameByType } from "../../utils/get-name-by-type";
import { sortFlows } from "../../utils/sort-flows";
import EmptyComponent from "../emptyComponent";
import HeaderComponent from "../headerComponent";
import { downloadFlow, removeApiKeys } from "../../../../utils/reactflowUtils";
import { useDarkStore } from "../../../../stores/darkStore";
import { UPLOAD_ERROR_ALERT } from "../../../../constants/alerts_constants";

export default function ComponentsComponent({
  type = "all",
}: {
  type?: string;
}) {
  const uploadFlow = useFlowsManagerStore((state) => state.uploadFlow);
  const removeFlow = useFlowsManagerStore((state) => state.removeFlow);
  const isLoading = useFlowsManagerStore((state) => state.isLoading);
  const setAllFlows = useFlowsManagerStore((state) => state.setAllFlows);
  const allFlows = useFlowsManagerStore((state) => state.allFlows);

  const flowsFromFolder = useFolderStore(
    (state) => state.selectedFolder?.flows,
  );

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const [openDelete, setOpenDelete] = useState(false);
  const searchFlowsComponents = useFlowsManagerStore(
    (state) => state.searchFlowsComponents,
  );

  const setSelectedFlowsComponentsCards = useFlowsManagerStore(
    (state) => state.setSelectedFlowsComponentsCards,
  );

  const selectedFlowsComponentsCards = useFlowsManagerStore(
    (state) => state.selectedFlowsComponentsCards,
  );

  const [handleFileDrop] = useFileDrop(uploadFlow, type)!;
  const [pageSize, setPageSize] = useState(20);
  const [pageIndex, setPageIndex] = useState(1);
  const navigate = useNavigate();
  const location = useLocation();
  const all: FlowType[] = sortFlows(allFlows, type);
  const start = (pageIndex - 1) * pageSize;
  const end = start + pageSize;
  const data: FlowType[] = all?.slice(start, end);

  const name = getNameByType(type);

  const folderId = location?.state?.folderId;
  const getFolderById = useFolderStore((state) => state.getFolderById);
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const getFoldersApi = useFolderStore((state) => state.getFoldersApi);
  const setFolderUrl = useFolderStore((state) => state.setFolderUrl);
  const addFlow = useFlowsManagerStore((state) => state.addFlow);

  useEffect(() => {
    setFolderUrl(folderId ?? "");
    setSelectedFlowsComponentsCards([]);
    handleSelectAll(false);
    getFolderById(folderId ? folderId : myCollectionId);
  }, [location]);

  useEffect(() => {
    const newFlows = cloneDeep(flowsFromFolder!);
    const filteredFlows = newFlows?.filter(
      (f) =>
        f.name.toLowerCase().includes(searchFlowsComponents.toLowerCase()) ||
        f.description
          .toLowerCase()
          .includes(searchFlowsComponents.toLowerCase()),
    );

    if (searchFlowsComponents === "") {
      setAllFlows(flowsFromFolder!);
    }

    setAllFlows(filteredFlows);
  }, [searchFlowsComponents]);

  const resetFilter = () => {
    setPageIndex(1);
    setPageSize(20);
  };

  const { getValues, control, setValue } = useForm();
  const entireFormValues = useWatch({ control });

  const methods = useForm();
  const handleSelectAll = (select) => {
    const flowsFromFolderIds = flowsFromFolder?.map((f) => f.id);
    if (select) {
      Object.keys(getValues()).forEach((key) => {
        if (!flowsFromFolderIds?.includes(key)) return;
        setValue(key, true);
      });
      return;
    }

    Object.keys(getValues()).forEach((key) => {
      setValue(key, false);
    });
  };

  const handleSelectOptionsChange = (action: string) => {
    const hasSelected = selectedFlowsComponentsCards?.length > 0;
    if (!hasSelected) {
      setErrorData({
        title: "No items selected",
        list: ["Please select items to delete"],
      });
      return;
    }
    if (action === "delete") {
      setOpenDelete(true);
    } else if (action === "duplicate") {
      handleDuplicate();
    } else if (action === "export") {
      handleExport();
    }
  };

  const handleDuplicate = () => {
    Promise.all(
      selectedFlowsComponentsCards.map((selectedFlow) =>
        addFlow(
          true,
          allFlows.find((flow) => flow.id === selectedFlow),
        ),
      ),
    ).then(() => {
      resetFilter();
      getFoldersApi(true);
      if (!folderId || folderId === myCollectionId) {
        getFolderById(folderId ? folderId : myCollectionId);
      }
      setSelectedFlowsComponentsCards([]);

      setSuccessData({ title: "Flows duplicated successfully" });
    });
  };

  const handleImport = () => {
    uploadFlow({ newProject: true, isComponent: false })
      .then(() => {
        resetFilter();
        getFoldersApi(true);
        if (!folderId || folderId === myCollectionId) {
          getFolderById(folderId ? folderId : myCollectionId);
        }
        setSelectedFlowsComponentsCards([]);

        setSuccessData({ title: "Flows imported successfully" });
      })
      .catch((error) => {
        setErrorData({
          title: UPLOAD_ERROR_ALERT,
          list: [error],
        });
      });
  };

  const version = useDarkStore((state) => state.version);

  const handleExport = () => {
    selectedFlowsComponentsCards.map((selectedFlowId) => {
      const selectedFlow = allFlows.find((flow) => flow.id === selectedFlowId);
      downloadFlow(
        removeApiKeys({
          id: selectedFlow!.id,
          data: selectedFlow!.data!,
          description: selectedFlow!.description,
          name: selectedFlow!.name,
          last_tested_version: version,
          is_component: false,
        }),
        selectedFlow!.name,
        selectedFlow!.description,
      );
    });
    setSuccessData({ title: "Flows exported successfully" });
  };

  const handleDeleteMultiple = () => {
    removeFlow(selectedFlowsComponentsCards)
      .then(() => {
        resetFilter();
        getFoldersApi(true);
        if (!folderId || folderId === myCollectionId) {
          getFolderById(folderId ? folderId : myCollectionId);
        }
        setSuccessData({
          title: "Selected items deleted successfully",
        });
      })
      .catch(() => {
        setErrorData({
          title: "Error deleting items",
          list: ["Please try again"],
        });
      });
  };

  useEffect(() => {
    if (!entireFormValues || Object.keys(entireFormValues).length === 0) return;
    const selectedFlows: string[] = Object.keys(entireFormValues).filter(
      (key) => {
        if (entireFormValues[key] === true) {
          return true;
        }
        return false;
      },
    );

    setSelectedFlowsComponentsCards(selectedFlows);
  }, [entireFormValues]);

  const getDescriptionModal = useMemo(() => {
    const getTypeLabel = (type) => {
      const labels = {
        all: "item",
        component: "component",
        flow: "flow",
      };
      return labels[type] || "";
    };

    const getPluralizedLabel = (type) => {
      const labels = {
        all: "items",
        component: "components",
        flow: "flows",
      };
      return labels[type] || "";
    };

    if (selectedFlowsComponentsCards?.length === 1) {
      return getTypeLabel(type);
    }
    return getPluralizedLabel(type);
  }, [selectedFlowsComponentsCards, type]);

  const getTotalRowsCount = () => {
    if (type === "all") return allFlows?.length;

    return allFlows?.filter(
      (f) => (f.is_component ?? false) === (type === "component"),
    )?.length;
  };

  return (
    <>
      {allFlows?.length > 0 && (
        <HeaderComponent
          handleDelete={() => handleSelectOptionsChange("delete")}
          handleSelectAll={handleSelectAll}
          handleDuplicate={() => handleSelectOptionsChange("duplicate")}
          handleExport={() => handleSelectOptionsChange("export")}
          handleImport={() => handleImport()}
          disableFunctions={!(selectedFlowsComponentsCards?.length > 0)}
        />
      )}

      <CardsWrapComponent
        onFileDrop={handleFileDrop}
        dragMessage={`Drag your ${name} here`}
      >
        <div className="flex h-full w-full flex-col justify-between">
          <div className="flex w-full flex-col gap-4">
            {!isLoading && data?.length === 0 ? (
              <EmptyComponent />
            ) : (
              <div className="grid w-full gap-4 md:grid-cols-2 lg:grid-cols-2">
                {isLoading === false && data?.length > 0 ? (
                  <>
                    {data?.map((item) => (
                      <FormProvider {...methods} key={item.id}>
                        <form>
                          <CollectionCardComponent
                            is_component={type === "component"}
                            data={{
                              is_component: item.is_component ?? false,
                              ...item,
                            }}
                            disabled={isLoading}
                            data-testid={"edit-flow-button-" + item.id}
                            button={
                              !item.is_component ? (
                                <Link to={"/flow/" + item.id}>
                                  <Button
                                    tabIndex={-1}
                                    variant="outline"
                                    size="sm"
                                    className="whitespace-nowrap"
                                    data-testid={"edit-flow-button-" + item.id}
                                  >
                                    <IconComponent
                                      name="ExternalLink"
                                      className="main-page-nav-button select-none"
                                    />
                                    Edit Flow
                                  </Button>
                                </Link>
                              ) : (
                                <></>
                              )
                            }
                            onClick={
                              !item.is_component
                                ? () => {
                                    navigate("/flow/" + item.id);
                                  }
                                : undefined
                            }
                            playground={!item.is_component}
                            control={control}
                          />
                        </form>
                      </FormProvider>
                    ))}
                  </>
                ) : (
                  <>
                    <SkeletonCardComponent />
                    <SkeletonCardComponent />
                  </>
                )}
              </div>
            )}
          </div>
          {!isLoading && data?.length > 0 && (
            <div className="relative py-6">
              <PaginatorComponent
                storeComponent={true}
                pageIndex={pageIndex}
                pageSize={pageSize}
                rowsCount={[10, 20, 50, 100]}
                totalRowsCount={getTotalRowsCount()}
                paginate={(pageSize, pageIndex) => {
                  setPageIndex(pageIndex);
                  setPageSize(pageSize);
                }}
              ></PaginatorComponent>
            </div>
          )}
        </div>
      </CardsWrapComponent>
      {openDelete && (
        <DeleteConfirmationModal
          open={openDelete}
          setOpen={setOpenDelete}
          onConfirm={handleDeleteMultiple}
          description={getDescriptionModal}
        >
          <></>
        </DeleteConfirmationModal>
      )}
    </>
  );
}
