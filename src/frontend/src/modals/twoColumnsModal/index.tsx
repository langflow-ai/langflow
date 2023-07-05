import { useContext, useEffect, useRef, useState } from "react";
import { FlowType } from "../../types/flow";
import { alertContext } from "../../contexts/alertContext";
import { classNames, validateNodes } from "../../utils";
import { typesContext } from "../../contexts/typesContext";
import {
    TerminalSquare,
    MessageSquare,
    Variable,
    Eraser,
    MessageSquarePlus,
} from "lucide-react";
import { sendAllProps } from "../../types/api";
import { ChatMessageType } from "../../types/chat";

import _ from "lodash";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "../../components/ui/dialog";
import { CHAT_FORM_DIALOG_SUBTITLE } from "../../constants";
import { Label } from "../../components/ui/label";
import { TabsContext } from "../../contexts/tabsContext";
import {
    Accordion,
    AccordionContent,
    AccordionItem,
    AccordionTrigger,
} from "../../components/ui/accordion";
import { Textarea } from "../../components/ui/textarea";
import { Badge } from "../../components/ui/badge";
import ToggleShadComponent from "../../components/toggleShadComponent";
import Dropdown from "../../components/dropdownComponent";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "../../components/ui/dropdown-menu";
import { Button } from "../../components/ui/button";

export default function TwoColumnsModal({
    title,
    description,
    open,
    setOpen,
}: {
    description: string;
    title: string;
    open: boolean;
    setOpen: Function;
}) {
    const isOpen = useRef(open);
    useEffect(() => {
        isOpen.current = open;
    }, [open]);

    function setModalOpen(x: boolean) {
        setOpen(x);
    }
    //UPDATE COLORS AND STYLE CLASSSES
    return (
        <Dialog open={open} onOpenChange={setModalOpen}>
            <DialogTrigger className="hidden"></DialogTrigger>
            <DialogContent className="min-w-[80vw]">
                <DialogHeader>
                    <DialogTitle className="flex items-center">
                        <span className="pr-2">{title}</span>
                        <TerminalSquare
                            className="h-6 w-6 text-gray-800 pl-1 dark:text-white"
                            aria-hidden="true"
                        />
                    </DialogTitle>
                    <DialogDescription>{description}</DialogDescription>
                </DialogHeader>

                <div className="flex h-[80vh] w-full mt-2 ">
                    <div className="w-2/5 h-full">
                    </div>
                    <div className="w-full">
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    );

}
TwoColumnsModal.first = ({children})=><div>{children}</div>
TwoColumnsModal.second = ({children})=><div>{children}</div>
