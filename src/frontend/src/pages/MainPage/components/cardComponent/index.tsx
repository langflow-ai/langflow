import React from "react";
import {
  ArrowTopRightOnSquareIcon,
  TrashIcon,
} from "@heroicons/react/24/outline";
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
  let color = flow.style?.color || "bg-blue-400";
  return (
    <Card className="group">
      <CardHeader>
        <CardTitle className="flex justify-between items-start">
          <div className="flex gap-4 items-center">
            <span
              className={
                "rounded-md w-10 h-10 flex items-center justify-center text-2xl " +
                color
              }
            >
              {emoji}
            </span>
            {flow.name}
          </div>
          <button
            onClick={() => {
              removeFlow(flow.id);
            }}
          >
            <TrashIcon className="w-5 text-primary opacity-0 group-hover:opacity-100 transition-all" />
          </button>
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
        <div className="flex gap-2 w-full justify-between items-end">
          <div className="flex flex-wrap gap-2">
            <Badge variant="secondary">{idx === 0 ? "Agent" : "Tool"}</Badge>
            {idx === 0 && (
              <Badge variant="secondary">
                <div className="w-3">
                  <OpenAiIcon />
                </div>
                <span className="text-base">&nbsp;</span>OpenAI+
              </Badge>
            )}
          </div>
          <Button
            variant="outline"
            size="sm"
            className="whitespace-nowrap opacity-0 group-hover:opacity-100 transition-all"
            onClick={() => {
              setTabIndex(idx);
              setActiveTab("myflow");
            }}
          >
            <ArrowTopRightOnSquareIcon className="w-4 mr-2" />
            Edit
          </Button>
        </div>
      </CardFooter>
    </Card>
  );
};
