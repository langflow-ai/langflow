import CodeAreaModal from "@/modals/codeAreaModal";
import ConfirmationModal from "@/modals/confirmationModal";
import EditNodeModal from "@/modals/editNodeModal";
import ShareModal from "@/modals/shareModal";
import { APIClassType } from "@/types/api";
import { FlowType } from "@/types/flow";
import React, { memo } from "react";

interface ToolbarModalsProps {
  // Modal visibility states
  showModalAdvanced: boolean;
  showconfirmShare: boolean;
  showOverrideModal: boolean;
  openModal: boolean;
  hasCode: boolean;

  // Setters for modal states
  setShowModalAdvanced: (value: boolean) => void;
  setShowconfirmShare: (value: boolean) => void;
  setShowOverrideModal: (value: boolean) => void;
  setOpenModal: (value: boolean) => void;

  // Data and handlers
  data: any;
  flowComponent: FlowType;
  handleOnNewValue: (value: string | string[]) => void;
  handleNodeClass: (apiClassType: APIClassType, type: string) => void;
  setToolMode: (value: boolean) => void;
  setSuccessData: (data: { title: string }) => void;
  addFlow: (params: { flow: FlowType; override: boolean }) => void;
  name?: string;
}

const ToolbarModals = memo(
  ({
    showModalAdvanced,
    showconfirmShare,
    showOverrideModal,
    openModal,
    hasCode,
    setShowModalAdvanced,
    setShowconfirmShare,
    setShowOverrideModal,
    setOpenModal,
    data,
    flowComponent,
    handleOnNewValue,
    handleNodeClass,
    setToolMode,
    setSuccessData,
    addFlow,
    name = "code",
  }: ToolbarModalsProps) => {
    // Handlers for confirmation modal
    const handleConfirm = () => {
      addFlow({
        flow: flowComponent,
        override: true,
      });
      setSuccessData({ title: `${data.id} successfully overridden!` });
      setShowOverrideModal(false);
    };

    const handleClose = () => {
      setShowOverrideModal(false);
    };

    const handleCancel = () => {
      addFlow({
        flow: flowComponent,
        override: true,
      });
      setSuccessData({ title: "New component successfully saved!" });
      setShowOverrideModal(false);
    };

    return (
      <>
        {showModalAdvanced && (
          <EditNodeModal
            data={data}
            open={showModalAdvanced}
            setOpen={setShowModalAdvanced}
          />
        )}

        {showconfirmShare && (
          <ShareModal
            open={showconfirmShare}
            setOpen={setShowconfirmShare}
            is_component={true}
            component={flowComponent}
          />
        )}

        {showOverrideModal && (
          <ConfirmationModal
            open={showOverrideModal}
            title="Replace"
            onConfirm={handleConfirm}
            onClose={handleClose}
            onCancel={handleCancel}
            cancelText="Create New"
            confirmationText="Replace"
            size="x-small"
            icon="SaveAll"
            index={6}
          >
            <ConfirmationModal.Content>
              <span>
                It seems {data.node?.display_name} already exists. Do you want
                to replace it with the current or create a new one?
              </span>
            </ConfirmationModal.Content>
          </ConfirmationModal>
        )}

        {hasCode && (
          <div className="hidden">
            {openModal && (
              <CodeAreaModal
                setValue={handleOnNewValue}
                open={openModal}
                setOpen={setOpenModal}
                dynamic={true}
                setNodeClass={(apiClassType, type) => {
                  handleNodeClass(apiClassType, type);
                  setToolMode(false);
                }}
                nodeClass={data.node}
                value={data.node?.template[name]?.value ?? ""}
                componentId={data.id}
              >
                <></>
              </CodeAreaModal>
            )}
          </div>
        )}
      </>
    );
  },
);

ToolbarModals.displayName = "ToolbarModals";

export default ToolbarModals;
