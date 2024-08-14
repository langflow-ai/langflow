import useAddFlow from "@/hooks/flows/use-add-flow";
import { useNavigate, useParams } from "react-router-dom";
import {
  Card,
  CardContent,
  CardDescription,
  CardTitle,
} from "../../../../components/ui/card";

export default function NewFlowCardComponent() {
  const addFlow = useAddFlow();
  const navigate = useNavigate();
  const { folderId } = useParams();

  return (
    <Card
      onClick={() => {
        addFlow().then((id) => {
          navigate(`/flow/${id}${folderId ? `/folder/${folderId}` : ""}`);
        });
      }}
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
