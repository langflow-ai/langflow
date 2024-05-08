import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import CollectionCardComponent from "../../../../components/cardComponent";
import CardsWrapComponent from "../../../../components/cardsWrapComponent";
import IconComponent from "../../../../components/genericIconComponent";
import PaginatorComponent from "../../../../components/paginatorComponent";
import { SkeletonCardComponent } from "../../../../components/skeletonCardComponent";
import { Button } from "../../../../components/ui/button";
import {
  CONSOLE_ERROR_MSG,
  UPLOAD_ALERT_LIST,
  WRONG_FILE_ERROR_ALERT,
} from "../../../../constants/alerts_constants";
import ConfirmationModal from "../../../../modals/confirmationModal";
import useAlertStore from "../../../../stores/alertStore";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { useUtilityStore } from "../../../../stores/utilityStore";
import { FlowType } from "../../../../types/flow";
import HeaderComponent from "../headerComponent";

export default function ComponentsComponent({
  is_component = true,
}: {
  is_component?: boolean;
}) {
  const addFlow = useFlowsManagerStore((state) => state.addFlow);
  const uploadFlow = useFlowsManagerStore((state) => state.uploadFlow);
  const removeFlow = useFlowsManagerStore((state) => state.removeFlow);
  const isLoading = useFlowsManagerStore((state) => state.isLoading);
  const flows = useFlowsManagerStore((state) => state.flows);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const addItem = useUtilityStore((state) => state.setSelectedItems);
  const [selectedItems, setSelectedItems] = useState([]);

  const [pageSize, setPageSize] = useState(20);
  const [pageIndex, setPageIndex] = useState(1);

  const navigate = useNavigate();
  const all: FlowType[] = flows
    .filter((f) => (f.is_component ?? false) === is_component)
    .sort((a, b) => {
      if (a?.updated_at && b?.updated_at) {
        return (
          new Date(b?.updated_at!).getTime() -
          new Date(a?.updated_at!).getTime()
        );
      } else if (a?.updated_at && !b?.updated_at) {
        return 1;
      } else if (!a?.updated_at && b?.updated_at) {
        return -1;
      } else {
        return (
          new Date(b?.date_created!).getTime() -
          new Date(a?.date_created!).getTime()
        );
      }
    });
  const start = (pageIndex - 1) * pageSize;
  const end = start + pageSize;
  const data: FlowType[] = all.slice(start, end);

  const name = is_component ? "Component" : "Flow";

  const onFileDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.types.some((types) => types === "Files")) {
      if (e.dataTransfer.files.item(0).type === "application/json") {
        uploadFlow({
          newProject: true,
          file: e.dataTransfer.files.item(0)!,
          isComponent: is_component,
        })
          .then(() => {
            setSuccessData({
              title: `${
                is_component ? "Component" : "Flow"
              } uploaded successfully`,
            });
          })
          .catch((error) => {
            setErrorData({
              title: CONSOLE_ERROR_MSG,
              list: [error],
            });
          });
      } else {
        setErrorData({
          title: WRONG_FILE_ERROR_ALERT,
          list: [UPLOAD_ALERT_LIST],
        });
      }
    }
  };
  function resetFilter() {
    setPageIndex(1);
    setPageSize(20);
  }

  const { getValues, control, setValue } = useForm<any>();

  const handleSelectAll = (select) => {
    if (select) {
      Object.keys(getValues()).forEach((key) => {
        setValue(key, true);
      });
      return;
    }

    Object.keys(getValues()).forEach((key) => {
      setValue(key, false);
    });
  };

  const handleSelectOptionsChange = (option) => {
    switch (option) {
      case "delete":
        break;
      default:
        break;
    }
  };

  return (
    <>
      <HeaderComponent
        handleSelectOptionsChange={handleSelectOptionsChange}
        handleSelectAll={handleSelectAll}
      />

      <CardsWrapComponent
        onFileDrop={onFileDrop}
        dragMessage={`Drag your ${name} here`}
      >
        <div className="flex h-full w-full flex-col justify-between">
          <div className="flex w-full flex-col gap-4">
            {!isLoading && data.length === 0 ? (
              <div className="mt-6 flex w-full items-center justify-center text-center">
                <div className="flex-max-width h-full flex-col">
                  <div className="flex w-full flex-col gap-4">
                    <div className="grid w-full gap-4">
                      Flows and components can be created using Langflow.
                    </div>
                    <div className="align-center flex w-full justify-center gap-1">
                      <span>New?</span>
                      <span className="transition-colors hover:text-muted-foreground">
                        <button
                          onClick={() => {
                            addFlow(true).then((id) => {
                              navigate("/flow/" + id);
                            });
                          }}
                          className="underline"
                        >
                          Start Here
                        </button>
                        .
                      </span>
                      <span className="animate-pulse">🚀</span>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="grid w-full gap-4 md:grid-cols-2 lg:grid-cols-2">
                {isLoading === false && data?.length > 0 ? (
                  <>
                    {data?.map((item, idx) => (
                      <form>
                        <CollectionCardComponent
                          onDelete={() => {
                            removeFlow(item.id);
                            setSuccessData({
                              title: `${
                                item.is_component ? "Component" : "Flow"
                              } deleted successfully!`,
                            });
                            resetFilter();
                          }}
                          key={idx}
                          data={{
                            is_component: item.is_component ?? false,
                            ...item,
                          }}
                          disabled={isLoading}
                          data-testid={
                            "edit-flow-button-" + item.id + "-" + idx
                          }
                          button={
                            !is_component ? (
                              <Link to={"/flow/" + item.id}>
                                <Button
                                  tabIndex={-1}
                                  variant="outline"
                                  size="sm"
                                  className="whitespace-nowrap "
                                  data-testid={
                                    "edit-flow-button-" + item.id + "-" + idx
                                  }
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
                            !is_component
                              ? () => {
                                  navigate("/flow/" + item.id);
                                }
                              : undefined
                          }
                          playground={!is_component}
                          control={control}
                        />
                      </form>
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
          {!isLoading && data.length > 0 && (
            <div className="relative py-6">
              <PaginatorComponent
                storeComponent={true}
                pageIndex={pageIndex}
                pageSize={pageSize}
                rowsCount={[10, 20, 50, 100]}
                totalRowsCount={
                  flows.filter(
                    (f) => (f.is_component ?? false) === is_component,
                  ).length
                }
                paginate={(pageSize, pageIndex) => {
                  setPageIndex(pageIndex);
                  setPageSize(pageSize);
                }}
              ></PaginatorComponent>
            </div>
          )}
        </div>
      </CardsWrapComponent>

      <ConfirmationModal
        title="Delete flows"
        titleHeader="Delete selected flows"
        modalContentTitle="Attention!"
        cancelText="Cancel"
        confirmationText="Delete"
        icon={"UserMinus2"}
        onConfirm={(index, keys) => {
          console.log("keys");
        }}
        size="x-small"
      >
        <ConfirmationModal.Content>
          <span>
            Are you sure you want to delete this key? This action cannot be
            undone.
          </span>
        </ConfirmationModal.Content>
        <ConfirmationModal.Trigger>
          <IconComponent
            name="Trash2"
            className="ml-2 h-4 w-4 cursor-pointer"
          />
        </ConfirmationModal.Trigger>
      </ConfirmationModal>
    </>
  );
}
