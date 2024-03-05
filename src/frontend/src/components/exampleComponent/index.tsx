import { useEffect, useState } from "react";
import { getComponent, postLikeComponent } from "../../controllers/API";
import DeleteConfirmationModal from "../../modals/DeleteConfirmationModal";
import useAlertStore from "../../stores/alertStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { useStoreStore } from "../../stores/storeStore";
import { storeComponent } from "../../types/store";
import cloneFLowWithParent from "../../utils/storeUtils";
import { cn } from "../../utils/utils";
import ShadTooltip from "../ShadTooltipComponent";
import IconComponent from "../genericIconComponent";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import {
    Card,
    CardDescription,
    CardFooter,
    CardHeader,
    CardTitle,
} from "../ui/card";
import { FlowType } from "../../types/flow";

export default function CollectionCardComponent({
    data,
}: {
    data: FlowType;
    authorized?: boolean;
}) {
    const addFlow = useFlowsManagerStore((state) => state.addFlow);

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
                            <IconComponent
                                className={cn(
                                    "flex-shrink-0 h-7 w-7 text-flow-icon",
                                )}
                                name="Group"
                            />
                            <ShadTooltip content={data.name}>
                                <div className="w-full truncate">{data.name}</div>
                            </ShadTooltip>
                        </CardTitle>
                    </div>
                    <CardDescription className="pb-2 pt-2">
                        <div className="truncate-doubleline">{data.description}</div>
                    </CardDescription>
                </CardHeader>
            </div>

            <CardFooter>
                <div className="flex w-full items-center justify-between gap-2">
                    <div className="flex w-full justify-end flex-wrap gap-2">
                        <Button
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
