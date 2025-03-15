import GenericIconComponent from "@/components/common/genericIconComponent";
import { DialogClose } from "@radix-ui/react-dialog";
import React, { useEffect, useState } from "react";
import ShadTooltip from "../../components/common/shadTooltipComponent";
import { Button } from "../../components/ui/button";
import {
  ConfirmationModalType,
  ContentProps,
  TriggerProps,
} from "../../types/components";
import BaseModal from "../baseModal";

const Content: React.FC<ContentProps> = ({ children }) => {
  return <div className="h-full w-full">{children}</div>;
};
const Trigger: React.FC<TriggerProps> = ({
  children,
  tooltipContent,
  side,
}: TriggerProps) => {
  return tooltipContent ? (
    <ShadTooltip side={side} content={tooltipContent}>
      <div className="h-full w-full">{children}</div>
    </ShadTooltip>
  ) : (
    <div className="h-full w-full">{children}</div>
  );
};
function ConfirmationModal({
  title,
  titleHeader,
  modalContentTitle,
  cancelText,
  confirmationText,
  children,
  destructive = false,
  destructiveCancel = false,
  icon,
  loading,
  data,
  index,
  onConfirm,
  open,
  onClose,
  onCancel,
  ...props
}: ConfirmationModalType) {
  const [modalOpen, setModalOpen] = useState(open ?? false);
  const [flag, setFlag] = useState(false);

  useEffect(() => {
    if (open) setModalOpen(open);
  }, [open]);

  useEffect(() => {
    if (onClose && modalOpen === false && !flag) {
      onClose();
    } else if (flag) {
      setFlag(false);
    }
  }, [modalOpen]);

  const triggerChild = React.Children.toArray(children).find(
    (child) => (child as React.ReactElement).type === Trigger,
  );
  const ContentChild = React.Children.toArray(children).find(
    (child) => (child as React.ReactElement).type === Content,
  );

  const shouldShowConfirm = confirmationText && onConfirm;
  const shouldShowCancel = cancelText;
  const shouldShowFooter = shouldShowConfirm || shouldShowCancel;

  const handleCancel = () => {
    setFlag(true);
    setModalOpen(false);
    onCancel?.();
  };

  return (
    <BaseModal {...props} open={open} setOpen={setModalOpen}>
      <BaseModal.Trigger>{triggerChild}</BaseModal.Trigger>
      <BaseModal.Header description={titleHeader ?? null}>
        <span className="pr-2">{title}</span>
        {icon && (
          <GenericIconComponent
            name={icon}
            className="text-foreground h-6 w-6 pl-1"
            aria-hidden="true"
          />
        )}
      </BaseModal.Header>
      <BaseModal.Content>
        {modalContentTitle && modalContentTitle != "" && (
          <>
            <strong>{modalContentTitle}</strong>
            <br></br>
          </>
        )}
        {ContentChild}
      </BaseModal.Content>

      {shouldShowFooter ? (
        <BaseModal.Footer>
          {shouldShowConfirm && (
            <Button
              className="ml-3"
              variant={destructive ? "destructive" : "default"}
              onClick={() => {
                setFlag(true);
                setModalOpen(false);
                onConfirm(index, data);
              }}
              loading={loading}
              data-testid="replace-button"
            >
              {confirmationText}
            </Button>
          )}
          {shouldShowCancel && (
            <DialogClose>
              <Button
                className=""
                variant={destructiveCancel ? "destructive" : "outline"}
                onClick={handleCancel}
              >
                {cancelText}
              </Button>
            </DialogClose>
          )}
        </BaseModal.Footer>
      ) : (
        <></>
      )}
    </BaseModal>
  );
}
ConfirmationModal.Content = Content;
ConfirmationModal.Trigger = Trigger;

export default ConfirmationModal;
