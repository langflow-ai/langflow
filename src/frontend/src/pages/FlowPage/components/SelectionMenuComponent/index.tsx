import { Dialog, Transition } from "@headlessui/react";
import { Fragment, useEffect, useRef, useState } from "react";
import { NodeToolbar } from "reactflow";

export default function SelectionMenu({onClick, nodes, isVisible}){
    const [isOpen, setIsOpen] = useState(false);
    const [isTransitioning, setIsTransitioning] = useState(false);
    const [lastNodes, setLastNodes] = useState(nodes);

    // nodes get saved to not be gone after the toolbar closes
    useEffect(() => {
        setLastNodes(nodes);
    }, [isOpen]);

    // transition starts after and ends before the toolbar closes
    useEffect(() => {
        if(isVisible){
            setIsOpen(true);
            setTimeout(() => {setIsTransitioning(true);}, 50);
            
        } else {
            setIsTransitioning(false)
            setTimeout(() => {setIsOpen(false);}, 500);
        }
    }, [isVisible]);

    return (
        <NodeToolbar isVisible={isOpen} offset={5} nodeId={lastNodes && lastNodes.length > 0 ? lastNodes.map((n) => n.id): [] }>
            <div className="overflow-hidden w-24 h-8">
            <div className={"transition-all ease-in-out duration-500 w-24 h-8 bg-white dark:bg-gray-800 rounded-md shadow-md border text-gray-700 dark:text-gray-300" + (isTransitioning ? " translate-y-0" : " translate-y-8")}>
                    Testeeee
                    </div>
            </div>
            </NodeToolbar>
    )
}
    

