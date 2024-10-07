import { getSpecificClassFromBuildStatus } from "@/CustomNodes/helpers/get-class-from-build-status";
import useIconStatus from "@/CustomNodes/hooks/use-icons-status";
import useUpdateValidationStatus from "@/CustomNodes/hooks/use-update-validation-status";
import useValidationStatusString from "@/CustomNodes/hooks/use-validation-status-string";
import ShadTooltip from "@/components/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import {
  RUN_TIMESTAMP_PREFIX,
  STATUS_BUILD,
  STATUS_BUILDING,
  STATUS_INACTIVE,
} from "@/constants/constants";
import { BuildStatus } from "@/constants/enums";
import { track } from "@/customization/utils/analytics";
import { useDarkStore } from "@/stores/darkStore";
import useFlowStore from "@/stores/flowStore";
import { useShortcutsStore } from "@/stores/shortcuts";
import { VertexBuildTypeAPI } from "@/types/api";
import { NodeDataType } from "@/types/flow";
import { findLastNode } from "@/utils/reactflowUtils";
import { classNames } from "@/utils/utils";
import { useEffect, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import IconComponent from "../../../../components/genericIconComponent";

export default function NodeStatus({
  nodeId,
  display_name,
  selected,
  setBorderColor,
  frozen,
  showNode,
  data,
}: {
  nodeId: string;
  display_name: string;
  selected: boolean;
  setBorderColor: (color: string) => void;
  frozen?: boolean;
  showNode: boolean;
  data: NodeDataType;
}) {
  const nodeId_ = data.node?.flow?.data
    ? (findLastNode(data.node?.flow.data!)?.id ?? nodeId)
    : nodeId;
  const [validationString, setValidationString] = useState<string>("");
  const [validationStatus, setValidationStatus] =
    useState<VertexBuildTypeAPI | null>(null);
  const buildStatus = useFlowStore((state) => {
    if (data.node?.flow && data.node.flow.data?.nodes) {
      const flow = data.node.flow;
      const nodes = flow.data?.nodes; // check all the build status of the nodes in the flow
      const buildStatus_: BuildStatus[] = [];
      //@ts-ignore
      for (const node of nodes) {
        buildStatus_.push(state.flowBuildStatus[node.id]?.status);
      }
      if (buildStatus_.every((status) => status === BuildStatus.BUILT)) {
        return BuildStatus.BUILT;
      }
      if (buildStatus_.some((status) => status === BuildStatus.BUILDING)) {
        return BuildStatus.BUILDING;
      }
      if (buildStatus_.some((status) => status === BuildStatus.ERROR)) {
        return BuildStatus.ERROR;
      } else {
        return BuildStatus.TO_BUILD;
      }
    }
    return state.flowBuildStatus[nodeId]?.status;
  });
  const lastRunTime = useFlowStore(
    (state) => state.flowBuildStatus[nodeId_]?.timestamp,
  );
  const iconStatus = useIconStatus(buildStatus, validationStatus);
  const buildFlow = useFlowStore((state) => state.buildFlow);
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const setNode = useFlowStore((state) => state.setNode);
  const version = useDarkStore((state) => state.version);
  const isDark = useDarkStore((state) => state.dark);

  function handlePlayWShortcut() {
    if (buildStatus === BuildStatus.BUILDING || isBuilding || !selected) return;
    setValidationStatus(null);
    buildFlow({ stopNodeId: nodeId });
  }

  const play = useShortcutsStore((state) => state.play);
  const flowPool = useFlowStore((state) => state.flowPool);
  useHotkeys(play, handlePlayWShortcut, { preventDefault: true });
  useValidationStatusString(validationStatus, setValidationString);
  useUpdateValidationStatus(nodeId_, flowPool, setValidationStatus);

  const getBaseBorderClass = (selected) => {
    let className = selected
      ? "border ring ring-[0.5px] ring-selected border-selected hover:shadow-node"
      : "border hover:shadow-node";
    let frozenClass = selected ? "border-ring-frozen" : "border-frozen";
    return frozen ? frozenClass : className;
  };

  const getNodeBorderClassName = (
    selected: boolean,
    showNode: boolean,
    buildStatus: BuildStatus | undefined,
    validationStatus: VertexBuildTypeAPI | null,
  ) => {
    const specificClassFromBuildStatus = getSpecificClassFromBuildStatus(
      buildStatus,
      validationStatus,
      isDark,
    );

    const baseBorderClass = getBaseBorderClass(selected);
    const names = classNames(baseBorderClass, specificClassFromBuildStatus);
    return names;
  };

  useEffect(() => {
    setBorderColor(
      getNodeBorderClassName(selected, showNode, buildStatus, validationStatus),
    );
  }, [selected, showNode, buildStatus, validationStatus, frozen]);

  useEffect(() => {
    if (buildStatus === BuildStatus.BUILT && !isBuilding) {
      setNode(
        nodeId,
        (old) => {
          return {
            ...old,
            data: {
              ...old.data,
              node: {
                ...old.data.node,
                lf_version: version,
              },
            },
          };
        },
        false,
      );
    }
  }, [buildStatus, isBuilding]);

  return (
    <>
      <div className="flex flex-shrink-0 items-center gap-2">
        <ShadTooltip
          content={
            buildStatus === BuildStatus.BUILDING ? (
              <span> {STATUS_BUILDING} </span>
            ) : buildStatus === BuildStatus.INACTIVE ? (
              <span> {STATUS_INACTIVE} </span>
            ) : !validationStatus ? (
              <span className="flex">{STATUS_BUILD}</span>
            ) : (
              <div className="max-h-100 p-2">
                <div className="max-h-80 overflow-auto">
                  {validationString && (
                    <div className="ml-1 pb-2 text-status-red">
                      {validationString}
                    </div>
                  )}
                  {lastRunTime && (
                    <div className="justify-left flex font-normal text-muted-foreground">
                      <div>{RUN_TIMESTAMP_PREFIX}</div>
                      <div className="ml-1 text-status-blue">{lastRunTime}</div>
                    </div>
                  )}
                </div>
                <div className="justify-left flex font-normal text-muted-foreground">
                  <div>Duration:</div>
                  <div className="ml-1 text-status-blue">
                    {validationStatus?.data.duration}
                  </div>
                </div>
              </div>
            )
          }
          side="bottom"
        >
          <div className="cursor-help">{iconStatus}</div>
        </ShadTooltip>
        {showNode && (
          <Button
            onClick={() => {
              if (buildStatus === BuildStatus.BUILDING || isBuilding) return;
              setValidationStatus(null);
              buildFlow({ stopNodeId: nodeId });
              track("Flow Build - Clicked", { stopNodeId: nodeId });
            }}
            unstyled
            className="group p-1"
          >
            <div data-testid={`button_run_` + display_name.toLowerCase()}>
              <IconComponent
                name="Play"
                className={
                  "h-5 w-5 fill-current stroke-2 text-muted-foreground transition-all group-hover:text-medium-indigo group-hover/node:opacity-100"
                }
              />
            </div>
          </Button>
        )}
      </div>
    </>
  );
}
