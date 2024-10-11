import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { track } from "@/customization/utils/analytics";
import useAddFlow from "@/hooks/flows/use-add-flow";
import { useParams } from "react-router-dom";
import {
  Card,
  CardContent,
  CardDescription,
  CardTitle,
} from "../../../../components/ui/card";

export default function NewFlowCardComponent() {
  const addFlow = useAddFlow();
  const navigate = useCustomNavigate();
  const { folderId } = useParams();

  const handleClick = () => {
    addFlow({ new_blank: true }).then((id) => {
      navigate(`/flow/${id}${folderId ? `/folder/${folderId}` : ""}`);
    });
    track("New Flow Created", { template: "Blank Flow" });
  };

  return (
    <Card
      onClick={handleClick}
      className="h-64 w-80 cursor-pointer bg-background pt-4"
      data-testid="blank-flow"
    >
      <CardContent className="h-full w-full">
        <div className="flex h-full w-full flex-col items-center justify-center rounded-md bg-muted align-middle bg-dotted-spacing-6 bg-dotted-muted-foreground bg-dotted-radius-px"></div>
      </CardContent>
      <CardDescription className="px-6 pb-4">
        <CardTitle className="text-lg text-primary">Blank Flow</CardTitle>
      </CardDescription>
    </Card>
  );
}
