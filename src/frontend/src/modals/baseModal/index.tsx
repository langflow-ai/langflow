import { ReactNode, useContext, useEffect, useRef } from "react";

import _ from "lodash";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "../../components/ui/dialog";
import React from "react";
import { PopUpContext } from "../../contexts/popUpContext";

type ContentProps = {children:ReactNode};
type HeaderProps = {children:ReactNode,description:string};


const Content: React.FC<ContentProps> = ({ children }) => {
    return (
        <div className="w-full h-full">
            {children}
        </div>)
}

const Header: React.FC<{ children: ReactNode, description:string }> = ({ children,description }) => {
    return (
        <DialogHeader>
            <DialogTitle className="flex items-center">
                {children}
            </DialogTitle>
            <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
    )
}
interface BaseModalProps {
    children: [React.ReactElement<ContentProps>, React.ReactElement<HeaderProps>];
    open: boolean;
    setOpen: (open: boolean) => void;
  }
function BaseModal({
    open,
    setOpen,
    children,
}: BaseModalProps) {
   const {closePopUp, setCloseEdit} = useContext(PopUpContext)

    function setModalOpen(x: boolean) {
        setOpen(x);
        if (x === false) {
          setTimeout(() => {
            setCloseEdit("editcode");
            closePopUp();
          }, 300);
        }
      }
    const headerChild = React.Children.toArray(children).find((child) => (child as React.ReactElement).type === Header);
    const ContentChild = React.Children.toArray(children).find(
        (child) => (child as React.ReactElement).type === Content
    );
    //UPDATE COLORS AND STYLE CLASSSES
    return (
        <Dialog open={open} onOpenChange={setModalOpen}>
            <DialogTrigger className="hidden"></DialogTrigger>
            <DialogContent className="min-w-[80vw]">
                {headerChild}
                <div className="flex h-[80vh] w-full mt-2 ">
                    {ContentChild}
                </div>
            </DialogContent>
        </Dialog>
    );

}

BaseModal.Content = Content;
BaseModal.Header = Header;
export default BaseModal;