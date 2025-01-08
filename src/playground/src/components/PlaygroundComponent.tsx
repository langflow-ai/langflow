import { TooltipProvider } from "@/components";
import PlaygroundButton from "./playgroundTrigger/trigger";

const PlaygroundComponent = () => {
    return (
        <TooltipProvider delayDuration={0}>
            <PlaygroundButton disable={true} />
        </TooltipProvider>

    );
};

export default PlaygroundComponent;