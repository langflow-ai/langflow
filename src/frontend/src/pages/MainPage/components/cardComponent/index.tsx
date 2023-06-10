import React from "react";
import {
  ArrowTopRightOnSquareIcon,
  TrashIcon,
} from "@heroicons/react/24/outline";
import { Edit, Trash } from "lucide-react";
import { OpenAiIcon } from "../../../../icons/OpenAi";
import { Button } from "../../../../components/ui/button";
import { Badge } from "../../../../components/ui/badge";
import {
  Card,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "../../../../components/ui/card";
import { FlowType } from "../../../../types/flow";
export const CardComponent = ({
  flow,
  idx,
  removeFlow,
  setTabIndex,
  setActiveTab,
}: {
  flow: FlowType;
  idx: number;
  removeFlow: (id: string) => void;
  setTabIndex: (idx: number) => void;
  setActiveTab: (tab: string) => void;
}) => {
  // flow has a style attribute
  // if it is empty just get a random style
  // if it is not empty use that style
  // if it is not empty and it is not a valid style get a random style

  let emoji = flow.style?.emoji || "🤖";
  // get random tailwind color
  let color = flow.style?.color || "bg-blue-200";
  return (
    <Card className="group">
      <CardHeader>
        <CardTitle className="flex justify-between items-start">
          <div className="flex gap-4 items-center">
            {/* <span
              className={
                "rounded-md w-10 h-10 flex items-center justify-center text-2xl " +
                color
              }
            >
              {emoji}
            </span> */}
            {flow.name}
          </div>
          <div className="flex gap-5">
            {/* make the icons shake a bit on hover */}
            <Edit
              className="w-4"
              onClick={() => {
                setTabIndex(idx);
                setActiveTab("myflow");
              }}
            />
            <Trash
              className="w-4"
              onClick={() => {
                removeFlow(flow.id);
              }}
            />
          </div>
        </CardTitle>
        <CardDescription className="pt-2 pb-2">
          <div className="truncate-doubleline">
            {idx === 0
              ? "This flow creates an agent that accesses a department store database and APIs to monitor customer activity and overall storage."
              : "This is a new Flow"}
            {/* {flow.description} */}
          </div>
        </CardDescription>
      </CardHeader>

      <CardFooter>
        <div className="flex gap-2 w-full justify-end items-end">
          {/* <div className="flex flex-wrap gap-2">
            <Badge variant="secondary">{idx === 0 ? "Agent" : "Tool"}</Badge>
            {idx === 0 && (
              <Badge variant="secondary">
                <div className="w-3">
                  <OpenAiIcon />
                </div>
                <span className="text-base">&nbsp;</span>OpenAI+
              </Badge>
            )}
          </div> */}
        </div>
      </CardFooter>
    </Card>
  );
};
