import { Dialog, Transition } from "@headlessui/react";
import { RectangleGroupIcon } from "@heroicons/react/24/outline";
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
            <div className="overflow-hidden w-28 h-10">
            <div className={"transition-all ease-in-out duration-500 px-2.5 w-24 h-10 bg-white dark:bg-gray-800 shadow-inner rounded-md border border-indigo-300 text-gray-700 dark:text-gray-300" + (isTransitioning ? " translate-y-0" : " translate-y-10")}>
                    <button className="w-full h-full flex justify-between items-center text-sm hover:text-indigo-500" onClick={onClick}><RectangleGroupIcon className="w-6"/>Group</button>
                    </div>
            </div>
            </NodeToolbar>
    )
}
    

