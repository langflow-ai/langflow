import { ReactNode, useEffect } from "react";

import React from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../../components/ui/dialog";

import {
  Dialog as Modal,
  DialogContent as ModalContent,
} from "../../components/ui/dialog-with-no-close";

import { DialogClose } from "@radix-ui/react-dialog";
import { Button } from "../../components/ui/button";
import { modalHeaderType } from "../../types/components";
import { cn } from "../../utils/utils";
import { switchCaseModalSize } from "./helpers/switch-case-size";

type ContentProps = { children: ReactNode };
type HeaderProps = { children: ReactNode; description: string };
type FooterProps = { children: ReactNode };
type TriggerProps = {
  children: ReactNode;
  asChild?: boolean;
  disable?: boolean;
  className?: string;
};

const Content: React.FC<ContentProps> = ({ children }) => {
  return <div className="flex h-full w-full flex-col">{children}</div>;
};
const Trigger: React.FC<TriggerProps> = ({
  children,
  asChild,
  disable,
  className,
}) => {
  return (
    <DialogTrigger
      className={asChild ? "" : cn("w-full", className)}
      hidden={children ? false : true}
      disabled={disable}
      asChild={asChild}
    >
      {children}
    </DialogTrigger>
  );
};

const Header: React.FC<{ children: ReactNode; description: string | null }> = ({
  children,
  description,
}: modalHeaderType): JSX.Element => {
  return (
    <DialogHeader>
      <DialogTitle className="flex items-center">{children}</DialogTitle>
      <DialogDescription>{description}</DialogDescription>
    </DialogHeader>
  );
};

const Footer: React.FC<{
  children?: ReactNode;
  submit?: {
    label: string;
    icon?: ReactNode;
    loading?: boolean;
    disabled?: boolean;
    dataTestId?: string;
  };
}> = ({ children, submit }) => {
  return submit ? (
    <div className="flex w-full items-center justify-between">
      {children ?? <div />}
      <div className="flex items-center gap-3">
        <DialogClose asChild>
          <Button variant="outline" type="button">
            Cancel
          </Button>
        </DialogClose>
        <Button
          data-testid={submit.dataTestId}
          type="submit"
          loading={submit.loading}
        >
          {submit.icon && submit.icon}
          {submit.label}
        </Button>
      </div>
    </div>
  ) : (
    <>{children && children}</>
  );
};
interface BaseModalProps {
  children: [
    React.ReactElement<ContentProps>,
    React.ReactElement<HeaderProps>,
    React.ReactElement<TriggerProps>?,
    React.ReactElement<FooterProps>?,
  ];
  open?: boolean;
  setOpen?: (open: boolean) => void;
  size?:
    | "x-small"
    | "smaller"
    | "small"
    | "medium"
    | "large"
    | "three-cards"
    | "large-thin"
    | "large-h-full"
    | "small-h-full"
    | "medium-h-full"
    | "md-thin"
    | "sm-thin"
    | "smaller-h-full"
    | "medium-log";

  disable?: boolean;
  onChangeOpenModal?: (open?: boolean) => void;
  type?: "modal" | "dialog";
  onSubmit?: () => void;
}
function BaseModal({
  open,
  setOpen,
  children,
  size = "large",
  onChangeOpenModal,
  type = "dialog",
  onSubmit,
}: BaseModalProps) {
  const headerChild = React.Children.toArray(children).find(
    (child) => (child as React.ReactElement).type === Header,
  );
  const triggerChild = React.Children.toArray(children).find(
    (child) => (child as React.ReactElement).type === Trigger,
  );
  const ContentChild = React.Children.toArray(children).find(
    (child) => (child as React.ReactElement).type === Content,
  );
  const ContentFooter = React.Children.toArray(children).find(
    (child) => (child as React.ReactElement).type === Footer,
  );

  let { minWidth, height } = switchCaseModalSize(size);

  useEffect(() => {
    if (onChangeOpenModal) {
      onChangeOpenModal(open);
    }
  }, [open]);

  //UPDATE COLORS AND STYLE CLASSSES
  return (
    <>
      {type === "modal" ? (
        <Modal open={open} onOpenChange={setOpen}>
          {triggerChild}
          <ModalContent className={cn(minWidth, "duration-300")}>
            <div className="truncate-doubleline word-break-break-word">
              {headerChild}
            </div>
            <div
              className={`flex flex-col ${height} w-full transition-all duration-300`}
            >
              {ContentChild}
            </div>
            {ContentFooter && (
              <div className="flex flex-row-reverse">{ContentFooter}</div>
            )}
          </ModalContent>
        </Modal>
      ) : (
        <Dialog open={open} onOpenChange={setOpen}>
          {triggerChild}
          <DialogContent className={cn(minWidth, "duration-300")}>
            <div className="truncate-doubleline word-break-break-word">
              {headerChild}
            </div>
            {onSubmit ? (
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  onSubmit();
                }}
                className="flex flex-col gap-6"
              >
                <div
                  className={`flex flex-col ${height} w-full transition-all duration-300`}
                >
                  {ContentChild}
                </div>
                {ContentFooter && (
                  <div className="flex flex-row-reverse">{ContentFooter}</div>
                )}
              </form>
            ) : (
              <>
                <div
                  className={`flex flex-col ${height} w-full transition-all duration-300`}
                >
                  {ContentChild}
                </div>
                {ContentFooter && (
                  <div className="flex flex-row-reverse">{ContentFooter}</div>
                )}
              </>
            )}
          </DialogContent>
        </Dialog>
      )}
    </>
  );
}

BaseModal.Content = Content;
BaseModal.Header = Header;
BaseModal.Trigger = Trigger;
BaseModal.Footer = Footer;
export default BaseModal;
