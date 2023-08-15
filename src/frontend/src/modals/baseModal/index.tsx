import { ReactNode } from "react";

import React from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../../components/ui/dialog";

type ContentProps = { children: ReactNode };
type HeaderProps = { children: ReactNode; description: string };
type FooterProps = { children: ReactNode };
type TriggerProps = { children: ReactNode };

const Content: React.FC<ContentProps> = ({ children }) => {
  return <div className="h-full w-full">{children}</div>;
};
const Trigger: React.FC<ContentProps> = ({ children }) => {
  return <>{children}</>;
};

const Header: React.FC<{ children: ReactNode; description: string }> = ({
  children,
  description,
}) => {
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
  disable?: boolean;
  size?: "smaller" | "small" | "medium" | "large" | "large-h-full";
}
function BaseModal({
  open,
  setOpen,
  disable = false,
  children,
  size = "large",
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
    case "smaller":
      minWidth = "min-w-[40vw]";
      height = "h-[27vh]";
      break;
    case "small":
      minWidth = "min-w-[40vw]";
      height = "h-[40vh]";
      break;
    case "medium":
      minWidth = "min-w-[60vw]";
      height = "h-[60vh]";
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

  //UPDATE COLORS AND STYLE CLASSSES
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        className={"w-full " + (disable ? "button-disable" : "")}
        hidden={triggerChild ? false : true}
      >
        {triggerChild}
      </DialogTrigger>
      <DialogContent className={minWidth}>
        {headerChild}
        <div className={`mt-2 flex flex-col ${height} w-full `}>
          {ContentChild}
        </div>
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
