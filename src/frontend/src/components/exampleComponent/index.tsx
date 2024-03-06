import { useNavigate } from "react-router-dom";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { FlowType } from "../../types/flow";
import { updateIds } from "../../utils/reactflowUtils";
import { cn } from "../../utils/utils";
import ShadTooltip from "../ShadTooltipComponent";
import IconComponent from "../genericIconComponent";
import { Button } from "../ui/button";
import {
    Card,
    CardDescription,
    CardFooter,
    CardHeader,
    CardTitle,
} from "../ui/card";

export default function CollectionCardComponent({
    flow,
}: {
    flow: FlowType;
    authorized?: boolean;
}) {
    const addFlow = useFlowsManagerStore((state) => state.addFlow);
    const navigate = useNavigate();
    const emojiRegex = /\p{Emoji}/u;
    const isEmoji = (str: string) => emojiRegex.test(str);

    return (
        <Card
            className={cn(
                "group relative h-48 w-2/6 flex flex-col justify-between overflow-hidden transition-all hover:shadow-md",
            )}
        >
            <div>
                <CardHeader>
                    <div>
                        <CardTitle className="flex w-full items-center justify-between gap-3 text-xl">
                            {flow.icon && isEmoji(flow.icon) && (
                                <div className="p-2 rounded-md flex align-middle items-center justify-center" style={{ backgroundColor: flow.icon_bg_color }}>

                                    <div className="pl-0.5 h-7 w-7">
                                        {flow.icon}
                                    </div>
                                </div>

                            )}
                            {(!flow.icon || !isEmoji(flow.icon)) &&
                                <div className="p-2 rounded-md flex align-middle items-center justify-center" style={{ backgroundColor: flow.icon_bg_color }}>
                                    <IconComponent
                                        className={cn(
                                            "flex-shrink-0 h-7 w-7 text-flow-icon",
                                        )}
                                        name={flow.icon || "Group"}
                                    />
                                </div>
                            }
                            <ShadTooltip content={flow.name}>
                                <div className="w-full truncate">{flow.name}</div>
                            </ShadTooltip>
                        </CardTitle>
                    </div>
                    <CardDescription className="pb-2 pt-2">
                        <ShadTooltip side="bottom" styleClasses="z-50" content={flow.description}>
                            <div className="truncate-doubleline">{flow.description}</div>
                        </ShadTooltip>
                    </CardDescription>
                </CardHeader>
            </div>

            <CardFooter>
                <div className="flex w-full items-center justify-between gap-2">
                    <div className="flex w-full flex-wrap justify-end gap-2">
                        <Button
                            onClick={() => {
                                updateIds(flow.data!);
                                addFlow(true, flow).then((id) => {
                                    navigate("/flow/" + id);
                                });
                            }}
                            tabIndex={-1}
                            variant="outline"
                            size="sm"
                            className="whitespace-nowrap "
                        >
                            <IconComponent
                                name="ExternalLink"
                                className="main-page-nav-button select-none"
                            />
                            Select Flow
                        </Button>
                    </div>
                </div>
            </CardFooter>
        </Card>
    );
}
