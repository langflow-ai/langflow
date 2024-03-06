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
    CardContent,
    CardDescription,
    CardFooter,
    CardHeader,
    CardTitle,
} from "../ui/card";
import { FlowType } from "../../types/flow";
import { useNavigate } from "react-router-dom";

export default function NewFlowCardComponent({
}: {
    }) {
    const addFlow = useFlowsManagerStore((state) => state.addFlow);
    const navigate = useNavigate();

    return (
        <Card

            className={cn(
                "group relative h-48 w-2/6 flex flex-col justify-between overflow-hidden transition-all hover:shadow-md",
            )}
        >
                <CardContent className="w-full h-full flex align-middle items-center justify-center">
            <button onClick={() => {
              addFlow(true).then((id) => {
                navigate("/flow/" + id);
              });
            }}>
                    <IconComponent
                        className={cn(
                            "h-12 w-12 text-muted-foreground",
                        )}
                        name="PlusCircle"
                    />
            </button>
                </CardContent>
        </Card>
    );
}
