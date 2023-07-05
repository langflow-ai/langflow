import { ReactNode, useEffect, useRef } from "react";
import {
    TerminalSquare,
} from "lucide-react";

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

const First: React.FC<{ children: ReactNode }> = ({ children }) => {
    return (
        <div className="w-2/5 h-full">
            {children}
        </div>)
}
const Second: React.FC<{ children: ReactNode }> = ({ children }) => {
    return (
        <div className="w-full">
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

function TwoColumnsModal({
    title,
    description,
    open,
    setOpen,
    children,
}: {
    children: ReactNode;
    description: string;
    title: string;
    open: boolean;
    setOpen: Function;
}, { }) {
    const isOpen = useRef(open);
    useEffect(() => {
        isOpen.current = open;
    }, [open]);

    function setModalOpen(x: boolean) {
        setOpen(x);
    }
    const firstChild = React.Children.toArray(children).find(
        (child) => (child as React.ReactElement).type === First
    );

    const secondChild = React.Children.toArray(children).find(
        (child) => (child as React.ReactElement).type === Second
    );
    const headerChild = React.Children.toArray(children).find((child) => (child as React.ReactElement).type === Header);
    //UPDATE COLORS AND STYLE CLASSSES
    return (
        <Dialog open={open} onOpenChange={setModalOpen}>
            <DialogTrigger className="hidden"></DialogTrigger>
            <DialogContent className="min-w-[80vw]">
                {headerChild}
                <div className="flex h-[80vh] w-full mt-2 ">
                    {firstChild}
                    {secondChild}
                </div>
            </DialogContent>
        </Dialog>
    );

}
TwoColumnsModal.First = First;
TwoColumnsModal.Second = Second;
TwoColumnsModal.Header = Header;
export default TwoColumnsModal;