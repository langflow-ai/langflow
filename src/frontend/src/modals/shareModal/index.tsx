import { Loader2 } from "lucide-react";
import { ReactNode, useContext, useEffect, useMemo, useState } from "react";
import EditFlowSettings from "../../components/EditFlowSettingsComponent";
import IconComponent from "../../components/genericIconComponent";
import { TagsSelector } from "../../components/tagsSelectorComponent";
import { Button } from "../../components/ui/button";
import { Checkbox } from "../../components/ui/checkbox";
import { alertContext } from "../../contexts/alertContext";
import { FlowsContext } from "../../contexts/flowsContext";
import { StoreContext } from "../../contexts/storeContext";
import { typesContext } from "../../contexts/typesContext";
import {
  getStoreComponents,
  getStoreTags,
  saveFlowStore,
  updateFlowStore,
} from "../../controllers/API";
import { FlowType } from "../../types/flow";
import {
  removeApiKeys,
  removeFileNameFromComponents,
} from "../../utils/reactflowUtils";
import { getTagsIds } from "../../utils/storeUtils";
import ConfirmationModal from "../ConfirmationModal";
import BaseModal from "../baseModal";

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
  const { version, addFlow } = useContext(FlowsContext);
  const { hasApiKey, hasStore } = useContext(StoreContext);
  const { setSuccessData, setErrorData } = useContext(alertContext);
  const { reactFlowInstance } = useContext(typesContext);
  const [checked, setChecked] = useState(false);
  const [name, setName] = useState(component?.name ?? "");
  const [description, setDescription] = useState(component?.description ?? "");
  const [internalOpen, internalSetOpen] = useState(children ? false : true);
  const [openConfirmationModal, setOpenConfirmationModal] = useState(false);
  const nameComponent = is_component ? "Component" : "Flow";

  const [tags, setTags] = useState<{ id: string; name: string }[]>([]);
  const [loadingTags, setLoadingTags] = useState<boolean>(false);
  const [sharePublic, setSharePublic] = useState(true);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [unavaliableNames, setUnavaliableNames] = useState<
    { id: string; name: string }[]
  >([]);
  const { saveFlow, flows, tabId } = useContext(FlowsContext);

  const [loadingNames, setLoadingNames] = useState(false);

  useEffect(() => {
    if (open || internalOpen) {
      if (hasApiKey && hasStore) {
        handleGetTags();
        handleGetNames();
      }
    }
  }, [open, internalOpen, hasApiKey, hasStore]);

  function handleGetTags() {
    setLoadingTags(true);
    getStoreTags().then((res) => {
      setTags(res);
      setLoadingTags(false);
    });
  }

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

  useEffect(() => {
    setName(component?.name ?? "");
    setDescription(component?.description ?? "");
  }, [component, open, internalOpen]);

  const handleShareComponent = async (update = false) => {
    //remove file names from flows before sharing
    removeFileNameFromComponents(component);
    const flow: FlowType = checked
      ? {
          id: component!.id,
          data: component!.data,
          description,
          name,
          last_tested_version: version,
          is_component: is_component,
        }
      : removeApiKeys({
          id: component!.id,
          data: component!.data,
          description,
          name,
          last_tested_version: version,
          is_component: is_component,
        });

    function successShare() {
      if (is_component) {
        addFlow(true, flow, update);
      } else {
        saveFlow(flow!, true);
      }
      setSuccessData({
        title: `${nameComponent} shared successfully`,
      });
    }

    if (!update)
      saveFlowStore(flow!, getTagsIds(selectedTags, tags), sharePublic).then(
        successShare,
        (err) => {
          setErrorData({
            title: "Error sharing " + is_component ? "component" : "flow",
            list: [err["response"]["data"]["detail"]],
          });
        }
      );
    else
      updateFlowStore(
        flow!,
        getTagsIds(selectedTags, tags),
        sharePublic,
        unavaliableNames.find((e) => e.name === name)!.id
      ).then(successShare, (err) => {
        setErrorData({
          title: "Error sharing " + is_component ? "component" : "flow",
          list: [err["response"]["data"]["detail"]],
        });
      });
  };

  const handleUpdateComponent = () => {
    handleShareComponent(true);
    if (setOpen) setOpen(false);
    else internalSetOpen(false);
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
            <span className=" text-xs text-destructive ">
              Warning: This action cannot be undone.
            </span>
          </ConfirmationModal.Content>
          <ConfirmationModal.Trigger>
            <></>
          </ConfirmationModal.Trigger>
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
        open={(!disabled && open) ?? internalOpen}
        setOpen={setOpen ?? internalSetOpen}
      >
        <BaseModal.Trigger>{children ? children : <></>}</BaseModal.Trigger>
        <BaseModal.Header
          description={`Share your ${nameComponent} to the Langflow Store.`}
        >
          <span className="pr-2">Share</span>
          <IconComponent
            name="Share2"
            className="h-6 w-6 pl-1 text-foreground"
            aria-hidden="true"
          />
        </BaseModal.Header>
        <BaseModal.Content>
          <div className="w-full rounded-lg border border-border p-4">
            <EditFlowSettings name={name} description={description} />
          </div>
          <div className="mt-3 flex h-8 w-full">
            <TagsSelector
              tags={tags}
              loadingTags={loadingTags}
              disabled={false}
              selectedTags={selectedTags}
              setSelectedTags={setSelectedTags}
            />
          </div>
          <div className="mt-5 flex items-center space-x-2">
            <Checkbox
              id="public"
              checked={sharePublic}
              onCheckedChange={(event: boolean) => {
                setSharePublic(event);
                setChecked(false);
              }}
            />
            <label htmlFor="public" className="export-modal-save-api text-sm ">
              Make {nameComponent} public
            </label>
          </div>
          <div className="mt-3 flex items-center space-x-2">
            <Checkbox
              id="terms"
              checked={checked}
              onCheckedChange={(event: boolean) => {
                setChecked(event);
              }}
              disabled={sharePublic}
            />
            <label htmlFor="terms" className="export-modal-save-api text-sm ">
              Save with my API keys
            </label>
          </div>
          <span className=" text-xs text-destructive ">
            Warning: Deselecting this box will exclusively eliminate API keys
            from fields explicitly designated for API keys.
          </span>
        </BaseModal.Content>

        <BaseModal.Footer>
          <div className="text-right">
            <Button
              disabled={loadingNames}
              type="button"
              onClick={() => {
                const isNameAvailable = !unavaliableNames.some(
                  (element) => element.name === name
                );

                if (isNameAvailable) {
                  handleShareComponent();
                  (setOpen || internalSetOpen)(false);
                } else {
                  setOpenConfirmationModal(true);
                }
              }}
            >
              {loadingNames ? (
                <>
                  <div className="center w-16">
                    <Loader2 className="m-auto h-4 w-4 animate-spin"></Loader2>
                  </div>
                </>
              ) : (
                <>
                  {is_component && !loadingNames ? "Save and " : ""}Share{" "}
                  {!is_component && !loadingNames ? "Flow" : ""}
                </>
              )}
            </Button>
          </div>
        </BaseModal.Footer>
      </BaseModal>
      <>{modalConfirmation}</>
    </>
  );
}
