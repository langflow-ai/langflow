import { Trash2, ExternalLink } from "lucide-react";
import { useContext } from "react";
import { Link } from "react-router-dom";
import { TabsContext } from "../../contexts/tabsContext";
import { FlowType } from "../../types/flow";
import { gradients } from "../../utils";
import {
  CardTitle,
  CardDescription,
  CardFooter,
  Card,
  CardHeader,
} from "../ui/card";

export const CardComponent = ({
  flow,
  id,
  onDelete,
  button,
}: {
  flow: FlowType;
  id: string;
  onDelete?: () => void;
  button?: JSX.Element;
}) => {
  const { removeFlow } = useContext(TabsContext);

  return (
    <Card className="group">
      <CardHeader>
        <CardTitle className="flex w-full items-center gap-4">
          <span
            className={
              "flex h-7 w-7 items-center justify-center rounded-full text-2xl " +
              gradients[parseInt(flow.id.slice(0, 12), 16) % gradients.length]
            }
          ></span>
          <span className="inline-block w-full flex-1 break-words truncate-doubleline">
            {flow.name}
          </span>
          {onDelete && (
            <button className="flex self-start" onClick={onDelete}>
              <Trash2 className="h-4 w-4 text-primary opacity-0 transition-all group-hover:opacity-100" />
            </button>
          )}
        </CardTitle>
        <CardDescription className="pb-2 pt-2">
          <div className="truncate-doubleline">
            {flow.description}
            {/* {flow.description} */}
          </div>
        </CardDescription>
      </CardHeader>

      <CardFooter>
        <div className="flex w-full items-end justify-between gap-2">
          <div className="flex flex-wrap gap-2">
            {/* <Badge variant="secondary">Agent</Badge>
            <Badge variant="secondary">
              <div className="w-3">
                <OpenAiIcon />
              </div>
              <span className="text-base">&nbsp;</span>OpenAI+
            </Badge> */}
          </div>
          {button && button}
        </div>
      </CardFooter>
    </Card>
  );
};
