import { ReactNode, useContext } from "react";

import React from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../../components/ui/dialog";
import { PopUpContext } from "../../contexts/popUpContext";

type ContentProps = { children: ReactNode };
type HeaderProps = { children: ReactNode; description: string };

const Content: React.FC<ContentProps> = ({ children }) => {
  return <div className="h-full w-full">{children}</div>;
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
interface BaseModalProps {
  children: [React.ReactElement<ContentProps>, React.ReactElement<HeaderProps>];
  open: boolean;
  setOpen: (open: boolean) => void;
  size?: "small" | "medium" | "large";
}
function BaseModal({
  open,
  setOpen,
  children,
  size = "large",
}: BaseModalProps) {
  const { closePopUp, setCloseEdit } = useContext(PopUpContext);

  function setModalOpen(x: boolean) {
    setOpen(x);
    if (x === false) {
      setTimeout(() => {
        setCloseEdit("editcode");
        closePopUp();
      }, 300);
    }
  }
  const headerChild = React.Children.toArray(children).find(
    (child) => (child as React.ReactElement).type === Header
  );
  const ContentChild = React.Children.toArray(children).find(
    (child) => (child as React.ReactElement).type === Content
  );

  let sizeClass = "";

  switch (size) {
    case "small":
      sizeClass = "min-w-[40vw]";
      break;
    case "medium":
      sizeClass = "min-w-[60vw]";
      break;
    case "large":
      sizeClass = "min-w-[80vw]";
      break;
    default:
      sizeClass = "min-w-[80vw]";
      break;
  }

  //UPDATE COLORS AND STYLE CLASSSES
  return (
    <Dialog open={true} onOpenChange={setModalOpen}>
      <DialogTrigger className="hidden"></DialogTrigger>
      <DialogContent className={sizeClass}>
        {headerChild}
        <div className="mt-2 flex h-[80vh] w-full ">{ContentChild}</div>
      </DialogContent>
    </Dialog>
  );
}

BaseModal.Content = Content;
BaseModal.Header = Header;
export default BaseModal;
