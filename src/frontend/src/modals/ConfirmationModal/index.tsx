import React, { useEffect, useState } from "react";
import ShadTooltip from "../../components/ShadTooltipComponent";
import { Button } from "../../components/ui/button";
import { ConfirmationModalType, ContentProps } from "../../types/components";
import { nodeIconsLucide } from "../../utils/styleUtils";
import BaseModal from "../baseModal";

const Content: React.FC<ContentProps> = ({ children }) => {
  return <div className="h-full w-full">{children}</div>;
};
const Trigger: React.FC<ContentProps> = ({
  children,
  tolltipContent,
  side,
}) => {
  return tolltipContent ? (
    <ShadTooltip side={side} content={tolltipContent}>
      <div className="h-full w-full">{children}</div>
    </ShadTooltip>
  ) : (
    <div className="h-full w-full">{children}</div>
  );
};
function ConfirmationModal({
  title,
  asChild,
  titleHeader,
  modalContentTitle,
  cancelText,
  confirmationText,
  children,
  destructive = false,
  icon,
  data,
  index,
  onConfirm,
  size,
  open,
  onClose,
  onCancel,
}: ConfirmationModalType) {
  const Icon: any = nodeIconsLucide[icon];
  const [modalOpen, setModalOpen] = useState(open ?? false);

  useEffect(() => {
    if (open) setModalOpen(open);
  }, [open]);

  useEffect(() => {
    if (onClose) onClose!(modalOpen);
  }, [modalOpen]);
  const triggerChild = React.Children.toArray(children).find(
    (child) => (child as React.ReactElement).type === Trigger
  );
  const ContentChild = React.Children.toArray(children).find(
    (child) => (child as React.ReactElement).type === Content
  );

  return (
    <BaseModal size={size} open={modalOpen} setOpen={setModalOpen}>
      <BaseModal.Trigger asChild={asChild}>{triggerChild}</BaseModal.Trigger>
      <BaseModal.Header description={titleHeader ?? null}>
        <span className="pr-2">{title}</span>
        <Icon
          name="icon"
          className="h-6 w-6 pl-1 text-foreground"
          aria-hidden="true"
        />
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

      <BaseModal.Footer>
        <Button
          className="ml-3"
          variant={destructive ? "destructive" : "default"}
          onClick={() => {
            setModalOpen(false);
            onConfirm(index, data);
          }}
        >
          {confirmationText}
        </Button>

        <Button
          className=""
          variant="outline"
          onClick={() => {
            if (onCancel) onCancel();
            setModalOpen(false);
          }}
        >
          {cancelText}
        </Button>
      </BaseModal.Footer>
    </BaseModal>
  );
}
ConfirmationModal.Content = Content;
ConfirmationModal.Trigger = Trigger;

export default ConfirmationModal;
