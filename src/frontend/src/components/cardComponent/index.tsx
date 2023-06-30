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
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "../ui/dialog";
import { Button } from "@mui/material";

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
              "rounded-full w-7 h-7 flex items-center justify-center text-2xl " +
              gradients[parseInt(flow.id.slice(0, 12), 16) % gradients.length]
            }
          ></span>
          <span className="flex-1 w-full inline-block truncate-doubleline break-words">
            {flow.name}
          </span>
          {onDelete && (
            <Dialog>
                <DialogTrigger asChild>
                <button className="flex self-start">
              <Trash2 className="w-4 h-4 text-primary opacity-0 group-hover:opacity-100 transition-all" />
            </button>
                </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Are you sure absolutely sure?</DialogTitle>
                <DialogDescription>
                  This action cannot be undone. Are you sure you want to permanently
                  delete this file from our servers?
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <Button type="submit" onClick={onDelete}>Confirm</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
          )}
        </CardTitle>
        <CardDescription className="pt-2 pb-2">
          <div className="truncate-doubleline">
            {flow.description}
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
          {button && button}
        </div>
      </CardFooter>
    </Card>
  );
};
