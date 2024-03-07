import { Card, CardContent, CardDescription, CardTitle } from "../ui/card";
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
        }} className="pt-4 w-80 h-64 cursor-pointer bg-background">
            <CardContent className="w-full h-full">
                <div className="bg-dotted-spacing-6 bg-dotted-muted-foreground bg-dotted-radius-px rounded-md bg-muted w-full h-full flex flex-col items-center align-middle justify-center">
                    
                </div>
            </CardContent>
            <CardDescription className="px-6 pb-4">
                <CardTitle className="text-primary text-lg">Blank Flow</CardTitle>
            </CardDescription>
        </Card>
    )
}