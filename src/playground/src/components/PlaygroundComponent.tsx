import { TooltipProvider } from "@/components";
import PlaygroundButton from "./playgroundTrigger/trigger";

function PlaygroundComponent() {

    return (
        <TooltipProvider delayDuration={0}>
            <PlaygroundButton disable={false} />
        </TooltipProvider>

    );
};

export default PlaygroundComponent;