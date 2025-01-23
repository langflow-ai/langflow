import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltipComponent from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useFlowStore from "@/stores/flowStore";

export default function DeployDropdown() {
    const domain = window.location.origin;
    const flowName = useFlowsManagerStore((state) => state.currentFlow?.name);
    const hasIO = useFlowStore((state) => state.hasIO);
    return (
        <DropdownMenu>
            <DropdownMenuTrigger asChild>
                <Button variant="default" className="font-medium">
                    Deploy
                    <IconComponent name="ChevronDown" className="icon-size font-medium" />
                </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
                sideOffset={10}
                alignOffset={-10}
                align="end"
                className="min-w-[300px] max-w-[400px]"
            >
                <ShadTooltipComponent
                    styleClasses="truncate"
                side="left"
                    content={hasIO ? `${domain}/${flowName}` : "Add a Chat Input or Chat Output to deploy the playground"}
                >
                    <DropdownMenuItem className="deploy-dropdown-item text-nowrap">
                        <div className={`group ${!hasIO ? "cursor-not-allowed !important text-muted-foreground" : ""}`}>
                            <IconComponent name="Globe" className="icon-size mr-2" />
                            <a
                                className={`max-w-[80%] truncate ${!hasIO ? "cursor-not-allowed" : ""}`}
                                href={`${domain}/${flowName}`}
                                target="_blank"
                                rel="noreferrer"
                                onClick={(event) => {
                                    if (!hasIO) {
                                        event.preventDefault();
                                    }
                                }}
                            >
                                {domain.replace(/^https?:\/\//, "")}/{flowName}
                            </a>
                            <div className="ml-auto w-[5%]">
                                <IconComponent
                                    name="ExternalLink"
                                    className="icon-size ml-auto opacity-0 group-hover:opacity-100"
                                />
                            </div>
                        </div>
                    </DropdownMenuItem>
                </ShadTooltipComponent>
                <DropdownMenuItem className="deploy-dropdown-item group">
                    <div>
                        <IconComponent name="Code2" className="icon-size mr-2" />
                        <span>API access</span>
                    </div>
                </DropdownMenuItem>
                <DropdownMenuItem className="deploy-dropdown-item group">
                    <div>
                        <IconComponent name="Columns2" className="icon-size mr-2" />
                        <span>Embed into site</span>
                    </div>
                </DropdownMenuItem>
                <DropdownMenuItem className="deploy-dropdown-item group">
                    <div className="group">
                        <IconComponent name="FileCode2" className="icon-size mr-2" />
                        <span>Langflow SDK</span>
                        <IconComponent
                            name="ExternalLink"
                            className="icon-size ml-auto hidden group-hover:block"
                        />
                    </div>
                </DropdownMenuItem>
            </DropdownMenuContent>
        </DropdownMenu>
    );
}
