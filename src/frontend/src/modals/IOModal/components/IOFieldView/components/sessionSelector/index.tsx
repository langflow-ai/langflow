import ShadTooltip from "@/components/shadTooltipComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import IconComponent from "@/components/genericIconComponent";
import useFlowStore from "@/stores/flowStore";

export default function SessionSelector({
    deleteSession,
    session,
    toggleVisibility,
    isVisible,
    inspectSession,
}: {
    deleteSession: (session: string) => void;
    session: string;
    toggleVisibility: () => void;
    isVisible: boolean;
    inspectSession: (session: string) => void;
}) {
    const currentFlowId = useFlowStore((state) => state.currentFlow?.id);
    return (
        <div className="file-component-accordion-div cursor-pointer">
            <div className="flex w-full items-center justify-between gap-2 overflow-hidden border-b px-2 py-3.5 align-middle">
                <ShadTooltip styleClasses="z-50" content={session}>
                    <div className="flex min-w-0">
                        <Badge variant="gray" size="md" className="block truncate">
                            {session === currentFlowId ? "Default Session" : session}
                        </Badge>
                    </div>
                </ShadTooltip>
                <div className="flex shrink-0 items-center justify-center gap-2 align-middle">
                    <Button unstyled size="icon" onClick={(e) => {
                        e.stopPropagation();
                        toggleVisibility();
                    }}>
                        <ShadTooltip styleClasses="z-50" content="Toggle Visibility">
                            <div>
                                <IconComponent name={!isVisible ? "EyeOff" : "Eye"} className="h-4 w-4" />
                            </div>
                        </ShadTooltip>
                    </Button>
                    <Button unstyled size="icon" onClick={(e) => {
                        e.stopPropagation();
                        inspectSession(session);
                    }}>
                        <ShadTooltip styleClasses="z-50" content="Table View">
                            <div>
                                <IconComponent name="Table" className="h-4 w-4" />
                            </div>
                        </ShadTooltip>
                    </Button>
                    <Button unstyled size="icon" onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        deleteSession(session);
                    }}>
                        <ShadTooltip styleClasses="z-50" content="Delete">
                            <div>
                                <IconComponent name="Trash2" className="h-4 w-4" />
                            </div>
                        </ShadTooltip>
                    </Button>
                </div>
            </div>
        </div>
    );
}