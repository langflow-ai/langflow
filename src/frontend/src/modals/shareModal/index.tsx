import useSaveFlow from "@/hooks/flows/use-save-flow";
import { useUtilityStore } from "@/stores/utilityStore";
import { cloneDeep } from "lodash";
import { ReactNode, useEffect, useMemo, useState } from "react";
import IconComponent from "../../components/common/genericIconComponent";
import { TagsSelector } from "../../components/common/tagsSelectorComponent";
import EditFlowSettings from "../../components/core/editFlowSettingsComponent";
import { Button } from "../../components/ui/button";
import { Checkbox } from "../../components/ui/checkbox";
import {
  getStoreComponents,
  saveFlowStore,
  updateFlowStore,
} from "../../controllers/API";
import useAlertStore from "../../stores/alertStore";
import { useDarkStore } from "../../stores/darkStore";
import { useStoreStore } from "../../stores/storeStore";
import { FlowType } from "../../types/flow";
import {
  downloadNode,
  removeApiKeys,
  removeFileNameFromComponents,
} from "../../utils/reactflowUtils";
import BaseModal from "../baseModal";
import ConfirmationModal from "../confirmationModal";
import ExportModal from "../exportModal";
import getTagsIds from "./utils/get-tags-ids";

export default function ShareModal({
  component,
  is_component,
  children,
  open,
  setOpen,
  disabled,
}: {
  children?: ReactNode;
  is_component: boolean;
  component: FlowType;
  open?: boolean;
  setOpen?: (open: boolean) => void;
  disabled?: boolean;
}): JSX.Element {
  const version = useDarkStore((state) => state.version);
  const hasStore = useStoreStore((state) => state.hasStore);
  const hasApiKey = useStoreStore((state) => state.hasApiKey);

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const [internalOpen, internalSetOpen] =
    setOpen !== undefined && open !== undefined
      ? [open, setOpen]
      : useState(children ? false : true);
  const [openConfirmationModal, setOpenConfirmationModal] = useState(false);
  const nameComponent = is_component ? "component" : "workflow";
  const [sharePublic, setSharePublic] = useState(true);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [unavaliableNames, setUnavaliableNames] = useState<
    { id: string; name: string }[]
  >([]);
  const saveFlow = useSaveFlow();
  const tags = useUtilityStore((state) => state.tags);

  const [loadingNames, setLoadingNames] = useState(false);

  const name = component?.name ?? "";
  const description = component?.description ?? "";

  useEffect(() => {
    if (internalOpen) {
      if (hasApiKey && hasStore) {
        handleGetNames();
      }
    }
  }, [internalOpen, hasApiKey, hasStore]);

  async function handleGetNames() {
    setLoadingNames(true);
    const unavaliableNames: Array<{ id: string; name: string }> = [];
    await getStoreComponents({
      fields: ["name", "id", "is_component"],
      filterByUser: true,
    }).then((res) => {
      res?.results?.forEach((element: any) => {
        if ((element.is_component ?? false) === is_component)
          unavaliableNames.push({ name: element.name, id: element.id });
      });
      setUnavaliableNames(unavaliableNames);
      setLoadingNames(false);
    });
  }

  const handleShareComponent = async (update = false) => {
    //remove file names from flows before sharing
    removeFileNameFromComponents(component);
    const flow: FlowType = removeApiKeys({
      id: component!.id,
      data: component!.data,
      description,
      name,
      last_tested_version: version,
      is_component: is_component,
    });

    function successShare() {
      if (!is_component) {
        saveFlow(flow);
      }
      setSuccessData({
        title: `${is_component ? "Component" : "Flow"} shared successfully!`,
      });
    }

    if (!update)
      saveFlowStore(
        flow!,
        getTagsIds(selectedTags, cloneDeep(tags) ?? []),
        sharePublic,
      ).then(successShare, (err) => {
        setErrorData({
          title: "Error sharing " + (is_component ? "component" : "flow"),
          list: [err["response"]["data"]["detail"]],
        });
      });
    else
      updateFlowStore(
        flow!,
        getTagsIds(selectedTags, cloneDeep(tags) ?? []),
        sharePublic,
        unavaliableNames.find((e) => e.name === name)!.id,
      ).then(successShare, (err) => {
        setErrorData({
          title: "Error sharing " + is_component ? "component" : "flow",
          list: [err["response"]["data"]["detail"]],
        });
      });
  };

  const handleUpdateComponent = () => {
    handleShareComponent(true);
    internalSetOpen(false);
  };

  const handleExportComponent = () => {
    component = removeApiKeys(component);
    downloadNode(component);
  };

  let modalConfirmation = useMemo(() => {
    return (
      <>
        <ConfirmationModal
          open={openConfirmationModal}
          title={`Replace`}
          cancelText="Cancel"
          confirmationText="Replace"
          size={"x-small"}
          icon={"SaveAll"}
          index={6}
          onConfirm={() => {
            handleUpdateComponent();
            setOpenConfirmationModal(false);
          }}
          onCancel={() => {
            setOpenConfirmationModal(false);
          }}
        >
          <ConfirmationModal.Content>
            <span>
              It seems {name} already exists. Do you want to replace it with the
              current?
            </span>
            <br></br>
            <span className="text-destructive text-xs">
              Note: This action is irreversible.
            </span>
          </ConfirmationModal.Content>
        </ConfirmationModal>
      </>
    );
  }, [
    unavaliableNames,
    name,
    loadingNames,
    handleShareComponent,
    openConfirmationModal,
  ]);

  return (
    <>
      <BaseModal
        size="smaller-h-full"
        open={!disabled && internalOpen}
        setOpen={internalSetOpen}
        onSubmit={() => {
          const isNameAvailable = !unavaliableNames.some(
            (element) => element.name === name,
          );

          if (isNameAvailable) {
            handleShareComponent();
            internalSetOpen(false);
          } else {
            setOpenConfirmationModal(true);
          }
        }}
      >
        <BaseModal.Trigger asChild>
          {children ? children : <></>}
        </BaseModal.Trigger>
        <BaseModal.Header
          description={`Publish ${
            is_component ? "your component" : "workflow"
          } to the Langflow Store.`}
        >
          <span className="pr-2">Share</span>
          <IconComponent
            name="Share3"
            className="text-foreground -m-0.5 h-6 w-6"
            aria-hidden="true"
          />
        </BaseModal.Header>
        <BaseModal.Content>
          {open && (
            <>
              <div className="border-border w-full rounded-lg border p-4">
                <EditFlowSettings name={name} description={description} />
              </div>
              <div className="mt-3 flex h-8 w-full">
                <TagsSelector
                  tags={tags ?? []}
                  loadingTags={false}
                  disabled={false}
                  selectedTags={selectedTags}
                  setSelectedTags={setSelectedTags}
                />
              </div>
              <div className="mt-5 mb-2 flex items-center space-x-2">
                <Checkbox
                  id="public"
                  checked={sharePublic}
                  onCheckedChange={(event: boolean) => {
                    setSharePublic(event);
                  }}
                  data-testid="public-checkbox"
                />
                <label
                  htmlFor="public"
                  className="export-modal-save-api text-sm"
                >
                  Set {nameComponent} status to public
                </label>
              </div>
              <span className="text-destructive text-xs">
                <b>Attention:</b> API keys in specified fields are automatically
                removed upon sharing.
              </span>
            </>
          )}
        </BaseModal.Content>

        <BaseModal.Footer
          submit={{
            label: `Share ${is_component ? "Component" : "Flow"}`,
            loading: loadingNames,
            dataTestId: "share-modal-button-flow",
          }}
        >
          <>
            {!is_component && (
              <ExportModal>
                <Button
                  type="button"
                  variant="outline"
                  className="gap-2"
                  onClick={() => {
                    // (setOpen || internalSetOpen)(false);
                  }}
                >
                  <IconComponent name="Download" className="h-4 w-4" />
                  Export
                </Button>
              </ExportModal>
            )}
            {is_component && (
              <Button
                type="button"
                variant="outline"
                className="gap-2"
                onClick={() => {
                  internalSetOpen(false);
                  handleExportComponent();
                }}
              >
                <IconComponent name="Download" className="h-4 w-4" />
                Export
              </Button>
            )}
          </>
        </BaseModal.Footer>
      </BaseModal>
      <>{modalConfirmation}</>
    </>
  );
}
