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

import { modalHeaderType } from "../../types/components";
import { cn } from "../../utils/utils";

type ContentProps = { children: ReactNode };
type HeaderProps = { children: ReactNode; description: string };
type FooterProps = { children: ReactNode };
type TriggerProps = {
  children: ReactNode;
  asChild?: boolean;
  disable?: boolean;
};

const Content: React.FC<ContentProps> = ({ children }) => {
  return <div className="flex h-full w-full flex-col">{children}</div>;
};
const Trigger: React.FC<TriggerProps> = ({ children, asChild, disable }) => {
  return (
    <DialogTrigger
      className={asChild ? "" : "w-full"}
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

const Footer: React.FC<{ children: ReactNode }> = ({ children }) => {
  return <>{children}</>;
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
    | "smaller-h-full";

  disable?: boolean;
  onChangeOpenModal?: (open?: boolean) => void;
  type?: "modal" | "dialog";
}
function BaseModal({
  open,
  setOpen,
  children,
  size = "large",
  onChangeOpenModal,
  type = "dialog",
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

  let minWidth: string;
  let height: string;

  switch (size) {
    case "x-small":
      minWidth = "min-w-[20vw]";
      height = " ";
      break;
    case "smaller":
      minWidth = "min-w-[40vw]";
      height = "h-[11rem]";
      break;
    case "smaller-h-full":
      minWidth = "min-w-[40vw]";
      height = "h-full";
      break;
    case "small":
      minWidth = "min-w-[40vw]";
      height = "h-[40vh]";
      break;
    case "small-h-full":
      minWidth = "min-w-[40vw]";
      break;
    case "medium":
      minWidth = "min-w-[60vw]";
      height = "h-[60vh]";
      break;
    case "medium-h-full":
      minWidth = "min-w-[60vw]";
      break;
    case "large":
      minWidth = "min-w-[85vw]";
      height = "h-[80vh]";
      break;
    case "three-cards":
      minWidth = "min-w-[1066px]";
      height = "h-fit";
      break;
    case "large-thin":
      minWidth = "min-w-[65vw]";
      height = "h-[80vh]";
      break;

    case "md-thin":
      minWidth = "min-w-[85vw]";
      height = "h-[70vh]";
      break;

    case "sm-thin":
      minWidth = "min-w-[65vw]";
      height = "h-[70vh]";
      break;

    case "large-h-full":
      minWidth = "min-w-[80vw]";
      break;
    default:
      minWidth = "min-w-[80vw]";
      height = "h-[80vh]";
      break;
  }

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
              className={`flex flex-col ${height!} w-full transition-all duration-300`}
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
            <div
              className={`flex flex-col ${height!} w-full transition-all duration-300`}
            >
              {ContentChild}
            </div>
            {ContentFooter && (
              <div className="flex flex-row-reverse">{ContentFooter}</div>
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
