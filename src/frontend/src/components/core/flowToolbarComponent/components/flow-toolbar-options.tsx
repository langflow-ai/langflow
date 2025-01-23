import { useState } from "react";
import PlaygroundButton from "./playground-button";
import useFlowStore from "@/stores/flowStore";
import DeployDropdown from "./deploy-dropdown";


export default function FlowToolbarOptions() {
    const [open, setOpen] = useState<boolean>(false);
    const hasIO = useFlowStore((state) => state.hasIO);

    return <div className="flex gap-1.5 items-center">
        <div className="flex h-full w-full gap-1.5 rounded-sm transition-all">
            <PlaygroundButton
                hasIO={hasIO}
                open={open}
                setOpen={setOpen}
                canvasOpen
            />
        </div>
        <DeployDropdown />
    </div>;
}
