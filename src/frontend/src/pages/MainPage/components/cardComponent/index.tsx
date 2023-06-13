import { Trash2, ExternalLink } from "lucide-react";
import { useContext } from "react";
import { Link } from "react-router-dom";
import { TabsContext } from "../../../../contexts/tabsContext";
import { FlowType } from "../../../../types/flow";
import { gradients } from "../../../../utils";
import { CardTitle, CardDescription, CardFooter, Card, CardHeader } from "../../../../components/ui/card";
import { Button } from "../../../../components/ui/button";

export const CardComponent = ({ flow, id }: { flow: FlowType; id: string }) => {
  const { removeFlow } = useContext(TabsContext);

  return (
    <Card className="group">
      <CardHeader>
        <CardTitle className="flex justify-between items-start">
          <div className="flex gap-4 items-center">
            <span
              className={
                "rounded-full w-8 h-8 flex items-center justify-center text-2xl " +
                gradients[parseInt(flow.id.slice(0, 6), 16) % gradients.length]
              }
            >
            </span>
            <span className="flex-1 truncate-doubleline">
              {flow.name}
            </span>
          </div>
          <button
            onClick={() => {
              removeFlow(flow.id);
            }}
          >
            <Trash2 className="w-5 text-primary opacity-0 group-hover:opacity-100 transition-all" />
          </button>
        </CardTitle>
        <CardDescription className="pt-2 pb-2">
          <div className="truncate-doubleline">
            This flow creates an agent that accesses a department store database
            and APIs to monitor customer activity and overall storage.
            {/* {flow.description} */}
          </div>
        </CardDescription>
      </CardHeader>

      <CardFooter>
        <div className="flex gap-2 w-full justify-between items-end">
          <div className="flex flex-wrap gap-2">
            {/* <Badge variant="secondary">Agent</Badge>
            <Badge variant="secondary">
              <div className="w-3">
                <OpenAiIcon />
              </div>
              <span className="text-base">&nbsp;</span>OpenAI+
            </Badge> */}
          </div>
          <Link to={"/flow/" + id}>
            <Button
              variant="outline"
              size="sm"
              className="whitespace-nowrap "
              
            >
              <ExternalLink className="w-4 mr-2" />
              Edit Flow
            </Button>
          </Link>
        </div>
      </CardFooter>
    </Card>
  );
};
