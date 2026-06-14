import { cloneDeep } from "lodash";
import { type ReactNode, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import useSaveFlow from "@/hooks/flows/use-save-flow";
import { useUtilityStore } from "@/stores/utilityStore";
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
import type { FlowType } from "../../types/flow";
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
  const { t } = useTranslation();
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
      // biome-ignore lint/suspicious/noExplicitAny: legacy
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
        title: t("share.sharedSuccessfully", {
          type: is_component ? t("deleteModal.component") : "Flow",
        }),
      });
    }

    if (!update)
      saveFlowStore(
        flow!,
        getTagsIds(selectedTags, cloneDeep(tags) ?? []),
        sharePublic,
      ).then(successShare, (err) => {
        setErrorData({
          title:
            t("errors.errorSharing") +
            " " +
            (is_component ? "component" : "flow"),
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
          title:
            t("errors.errorSharing") +
            " " +
            (is_component ? "component" : "flow"),
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

  const modalConfirmation = useMemo(() => {
    return (
      <>
        <ConfirmationModal
          open={openConfirmationModal}
          title={t("flow.replaceComponent")}
          cancelText={t("modal.cancelButton")}
          confirmationText={t("flow.replaceComponent")}
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
            <span>{t("share.replaceExisting", { name })}</span>
            <br></br>
            <span className="text-xs text-destructive">
              {t("share.thisActionIrreversible")}
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
          description={t("share.publishDescription", {
            type: is_component
              ? t("shareModal.yourComponent")
              : t("shareModal.workflow"),
          })}
        >
          <span className="pr-2">{t("misc.share")}</span>
          <IconComponent
            name="Share3"
            className="-m-0.5 h-6 w-6 text-foreground"
            aria-hidden="true"
          />
        </BaseModal.Header>
        <BaseModal.Content>
          {open && (
            <>
              <div className="w-full rounded-lg border border-border p-4">
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
              <div className="mb-2 mt-5 flex items-center space-x-2">
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
                  {t("share.setStatusPublic", { name: nameComponent })}
                </label>
              </div>
              <span className="text-xs text-destructive">
                <b>{t("modal.attention")}</b> {t("share.attentionApiKeys")}
              </span>
            </>
          )}
        </BaseModal.Content>

        <BaseModal.Footer
          submit={{
            label: is_component
              ? t("share.shareComponent")
              : t("share.shareFlow"),
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
                  {t("misc.export")}
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
                {t("misc.export")}
              </Button>
            )}
          </>
        </BaseModal.Footer>
      </BaseModal>
      <>{modalConfirmation}</>
    </>
  );
}
