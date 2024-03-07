import { useNavigate } from "react-router-dom";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { cn } from "../../utils/utils";
import IconComponent from "../genericIconComponent";
import { Card, CardContent } from "../ui/card";

export default function NewFlowCardComponent({}: {}) {
  const addFlow = useFlowsManagerStore((state) => state.addFlow);
  const navigate = useNavigate();

  return (
    <Card
      className={cn(
        "group relative flex h-48 w-2/6 flex-col justify-between overflow-hidden transition-all hover:shadow-md"
      )}
    >
      <CardContent className="flex h-full w-full items-center justify-center align-middle">
        <button
          onClick={() => {
            addFlow(true).then((id) => {
              navigate("/flow/" + id);
            });
          }}
        >
          <IconComponent
            className={cn("h-12 w-12 text-muted-foreground")}
            name="PlusCircle"
          />
        </button>
      </CardContent>
    </Card>
  );
}
