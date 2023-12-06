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
import { modalHeaderType } from "../../types/components";

type ContentProps = { children: ReactNode };
type HeaderProps = { children: ReactNode; description: string };
type FooterProps = { children: ReactNode };
type TriggerProps = {
  children: ReactNode;
  asChild?: boolean;
  disable?: boolean;
};

const Content: React.FC<ContentProps> = ({ children }) => {
  return <div className="h-full w-full">{children}</div>;
};
const Trigger: React.FC<TriggerProps> = ({ children, asChild, disable }) => {
  return (
    <DialogTrigger
      className={asChild ? "" : "w-full"}
      hidden={children ? false : true}
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
    React.ReactElement<FooterProps>?
  ];
  open?: boolean;
  setOpen?: (open: boolean) => void;
  size?:
    | "x-small"
    | "smaller"
    | "small"
    | "medium"
    | "large"
    | "large-h-full"
    | "small-h-full"
    | "medium-h-full"
    | "smaller-h-full";

  disable?: boolean;
  onChangeOpenModal?: (open?: boolean) => void;
}
function BaseModal({
  open,
  setOpen,
  children,
  size = "large",
  onChangeOpenModal,
}: BaseModalProps) {
  const headerChild = React.Children.toArray(children).find(
    (child) => (child as React.ReactElement).type === Header
  );
  const triggerChild = React.Children.toArray(children).find(
    (child) => (child as React.ReactElement).type === Trigger
  );
  const ContentChild = React.Children.toArray(children).find(
    (child) => (child as React.ReactElement).type === Content
  );
  const ContentFooter = React.Children.toArray(children).find(
    (child) => (child as React.ReactElement).type === Footer
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
      minWidth = "min-w-[80vw]";
      height = "h-[80vh]";
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
    <Dialog open={open} onOpenChange={setOpen}>
      {triggerChild}
      <DialogContent className={minWidth}>
        <div className="truncate-doubleline word-break-break-word">
          {headerChild}
        </div>
        <div className={`flex flex-col ${height!} w-full `}>{ContentChild}</div>
        {ContentFooter && (
          <div className="flex flex-row-reverse">{ContentFooter}</div>
        )}
      </DialogContent>
    </Dialog>
  );
}

BaseModal.Content = Content;
BaseModal.Header = Header;
BaseModal.Trigger = Trigger;
BaseModal.Footer = Footer;
export default BaseModal;
