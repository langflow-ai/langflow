import { Card, CardContent } from "../ui/card";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { useNavigate } from "react-router-dom";
import IconComponent from "../genericIconComponent";
import { cn } from "../../utils/utils";

export default function NewFlowCardComponent() {
    const addFlow = useFlowsManagerStore((state) => state.addFlow);
    const navigate = useNavigate();
    return (
        <Card onClick={() => {
            addFlow(true).then((id) => {
                navigate("/flow/" + id);
            });
        }} className="pt-4 w-80 h-72 cursor-pointer">
            <CardContent className="w-full h-full flex flex-col items-center align-middle justify-center">
                        
                    <IconComponent
                        className={cn("h-12 w-12 text-muted-foreground")}
                        name="SquarePen"
                    />
                    <div className="text-center text-muted-foreground"> Create from scratch</div>
            </CardContent>
        </Card>
    )
}