import React, { useContext, useState } from "react";
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
import RenameLabel from "../../../../components/ui/rename-label";
import _ from "lodash";
import { TabsContext } from "../../../../contexts/tabsContext";
import { alertContext } from "../../../../contexts/alertContext";
import { updateFlowInDatabase } from "../../../../controllers/API";
import { Link } from "react-router-dom";
export const CardComponent = ({
  flow,
  idx,
  removeFlow,
  setTabIndex,
}: {
  flow: FlowType;
  idx: number;
  removeFlow: (id: string) => void;
  setTabIndex: (idx: number) => void;
}) => {
  const { setErrorData } = useContext(alertContext);
  const { updateFlow } = useContext(TabsContext);
  function handleSaveFlow(flow) {
    try {
      updateFlowInDatabase(flow);
      updateFlow(flow);
      // updateFlowStyleInDataBase(flow);
    } catch (err) {
      setErrorData(err);
    }
  }
  const [rename, setRename] = useState(false);

  return (
    <Card className="group">
      <CardHeader>
        <CardTitle className="flex justify-between items-start">
          <div className="flex gap-4 items-center">
            <RenameLabel
              value={flow.name}
              setValue={(value) => {
                if (value !== "") {
                  let newFlow = _.cloneDeep(flow);
                  newFlow.name = value;
                  handleSaveFlow(newFlow);
                }
              }}
              rename={rename}
              setRename={setRename}
            />
          </div>
          <div className="flex gap-5">
            <Link to={`/flow/${flow.id}`}>
            <Edit
              className="w-4"
              onClick={() => {
                setTabIndex(idx);

              }}
            />
            </Link>
            <Trash
              className="w-4"
              onClick={() => {
                removeFlow(flow.id);
              }}
            />
          </div>
        </CardTitle>
        <CardDescription className="pt-2 pb-2 h-10">
          {/* <div className="flex gap-2"> */}
          <RenameLabel
            className="truncate-doubleline w-full h-full"
            placeholder="Description"
            value={flow.description || "Description"}
            setValue={(value) => {
              if (value !== "") {
                let newFlow = _.cloneDeep(flow);
                newFlow.description = value;
                handleSaveFlow(newFlow);
              }
            }}
            rename={rename}
            setRename={setRename}
          />
          {/* </div> */}
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
