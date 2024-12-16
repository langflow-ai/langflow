import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { usePostValidateComponentCode } from "@/controllers/API/queries/nodes/use-post-validate-component-code";
import { useEffect, useMemo, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { useUpdateNodeInternals } from "reactflow";
import { Button } from "../../components/ui/button";
import {
  TOOLTIP_HIDDEN_OUTPUTS,
  TOOLTIP_OPEN_HIDDEN_OUTPUTS,
} from "../../constants/constants";
import NodeToolbarComponent from "../../pages/FlowPage/components/nodeToolbarComponent";
import useAlertStore from "../../stores/alertStore";
import useFlowStore from "../../stores/flowStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { useShortcutsStore } from "../../stores/shortcuts";
import { useTypesStore } from "../../stores/typesStore";
import { OutputFieldType, VertexBuildTypeAPI } from "../../types/api";
import { NodeDataType } from "../../types/flow";
import { checkHasToolMode } from "../../utils/reactflowUtils";
import { classNames, cn } from "../../utils/utils";

import { processNodeAdvancedFields } from "../helpers/process-node-advanced-fields";
import useCheckCodeValidity from "../hooks/use-check-code-validity";
import useUpdateNodeCode from "../hooks/use-update-node-code";
import sortFields from "../utils/sort-fields";
import NodeDescription from "./components/NodeDescription";
import NodeName from "./components/NodeName";
import { OutputParameter } from "./components/NodeOutputParameter";
import NodeStatus from "./components/NodeStatus";
import RenderInputParameters from "./components/RenderInputParameters";
import { NodeIcon } from "./components/nodeIcon";
import { useBuildStatus } from "./hooks/use-get-build-status";

export const sortToolModeFields = (
  a: string,
  b: string,
  template: any,
  fieldOrder: string[],
  isToolMode: boolean,
) => {
  if (!isToolMode) return sortFields(a, b, fieldOrder);

  const aToolMode = template[a]?.tool_mode ?? false;
  const bToolMode = template[b]?.tool_mode ?? false;

  // If one is tool_mode and the other isn't, tool_mode goes last
  if (aToolMode && !bToolMode) return 1;
  if (!aToolMode && bToolMode) return -1;

  // If both are tool_mode or both aren't, use regular field order
  return sortFields(a, b, fieldOrder);
};

export default function GenericNode({
  data,
  selected,
}: {
  data: NodeDataType;
  selected: boolean;
  xPos?: number;
  yPos?: number;
}): JSX.Element {
  const types = useTypesStore((state) => state.types);
  const templates = useTypesStore((state) => state.templates);
  const deleteNode = useFlowStore((state) => state.deleteNode);
  const setNode = useFlowStore((state) => state.setNode);
  const updateNodeInternals = useUpdateNodeInternals();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
  const [isOutdated, setIsOutdated] = useState(false);
  const [isUserEdited, setIsUserEdited] = useState(false);
  const [borderColor, setBorderColor] = useState<string>("");
  const showNode = data.showNode ?? true;

  const updateNodeCode = useUpdateNodeCode(
    data?.id,
    data.node!,
    setNode,
    setIsOutdated,
    setIsUserEdited,
    updateNodeInternals,
  );

  if (!data.node!.template) {
    setErrorData({
      title: `Error in component ${data.node!.display_name}`,
      list: [
        `The component ${data.node!.display_name} has no template.`,
        `Please contact the developer of the component to fix this issue.`,
      ],
    });
    takeSnapshot();
    deleteNode(data.id);
  }

  useCheckCodeValidity(data, templates, setIsOutdated, setIsUserEdited, types);

  const [loadingUpdate, setLoadingUpdate] = useState(false);

  const [showHiddenOutputs, setShowHiddenOutputs] = useState(false);

  const { mutate: validateComponentCode } = usePostValidateComponentCode();

  const edges = useFlowStore((state) => state.edges);

  const handleUpdateCode = () => {
    setLoadingUpdate(true);
    takeSnapshot();
    // to update we must get the code from the templates in useTypesStore
    const thisNodeTemplate = templates[data.type]?.template;
    // if the template does not have a code key
    // return
    if (!thisNodeTemplate?.code) return;

    const currentCode = thisNodeTemplate.code.value;
    if (data.node) {
      validateComponentCode(
        { code: currentCode, frontend_node: data.node },
        {
          onSuccess: ({ data: resData, type }) => {
            if (resData && type && updateNodeCode) {
              const newNode = processNodeAdvancedFields(
                resData,
                edges,
                data.id,
              );

              updateNodeCode(newNode, currentCode, "code", type);
              setLoadingUpdate(false);
            }
          },
          onError: (error) => {
            setErrorData({
              title: "Error updating Compoenent code",
              list: [
                "There was an error updating the Component.",
                "If the error persists, please report it on our Discord or GitHub.",
              ],
            });
            console.log(error);
            setLoadingUpdate(false);
          },
        },
      );
    }
  };

  function handleUpdateCodeWShortcut() {
    if (isOutdated && selected) {
      handleUpdateCode();
    }
  }

  const shownOutputs =
    data.node!.outputs?.filter((output) => !output.hidden) ?? [];

  const hiddenOutputs =
    data.node!.outputs?.filter((output) => output.hidden) ?? [];

  const update = useShortcutsStore((state) => state.update);
  useHotkeys(update, handleUpdateCodeWShortcut, { preventDefault: true });

  const shortcuts = useShortcutsStore((state) => state.shortcuts);

  const [openShowMoreOptions, setOpenShowMoreOptions] = useState(false);

  const renderOutputs = (outputs) => {
    return outputs.map((output, idx) => (
      <OutputParameter
        key={output.name + idx}
        output={output}
        idx={
          data.node!.outputs?.findIndex((out) => out.name === output.name) ??
          idx
        }
        lastOutput={idx === outputs.length - 1}
        data={data}
        types={types}
        selected={selected}
        showNode={showNode}
        isToolMode={isToolMode}
      />
    ));
  };

  useEffect(() => {
    if (hiddenOutputs && hiddenOutputs.length == 0) {
      setShowHiddenOutputs(false);
    }
  }, [hiddenOutputs]);

  const memoizedNodeToolbarComponent = useMemo(() => {
    return selected ? (
      <div className={cn("absolute -top-12 left-1/2 z-50 -translate-x-1/2")}>
        <NodeToolbarComponent
          data={data}
          deleteNode={(id) => {
            takeSnapshot();
            deleteNode(id);
          }}
          setShowNode={(show) => {
            setNode(data.id, (old) => ({
              ...old,
              data: { ...old.data, showNode: show },
            }));
          }}
          numberOfOutputHandles={shownOutputs.length ?? 0}
          showNode={showNode}
          openAdvancedModal={false}
          onCloseAdvancedModal={() => {}}
          updateNode={handleUpdateCode}
          isOutdated={isOutdated && isUserEdited}
          setOpenShowMoreOptions={setOpenShowMoreOptions}
        />
      </div>
    ) : (
      <></>
    );
  }, [
    data,
    deleteNode,
    takeSnapshot,
    setNode,
    showNode,
    updateNodeCode,
    isOutdated,
    isUserEdited,
    selected,
    shortcuts,
  ]);

  const isToolMode =
    data.node?.outputs?.some((output) => output.name === "component_as_tool") ??
    false;

  const buildStatus = useBuildStatus(data, data.id);
  const hasOutputs = data.node?.outputs && data.node?.outputs.length > 0;
  const [validationStatus, setValidationStatus] =
    useState<VertexBuildTypeAPI | null>(null);
  const getValidationStatus = (data) => {
    setValidationStatus(data);
    return null;
  };

  const hasToolMode = checkHasToolMode(data.node?.template ?? {});

  return (
    <div className={cn(isOutdated && !isUserEdited ? "relative -mt-10" : "")}>
      <div
        className={cn(
          borderColor,
          showNode ? "w-80" : `w-48`,
          "generic-node-div group/node relative rounded-xl shadow-sm hover:shadow-md",
          !hasOutputs && "pb-4",
        )}
      >
        {memoizedNodeToolbarComponent}
        {isOutdated && !isUserEdited && (
          <div className="flex h-10 w-full items-center gap-4 rounded-t-[0.69rem] bg-warning p-2 px-4 text-warning-foreground">
            <ForwardedIconComponent
              name="AlertTriangle"
              strokeWidth={1.5}
              className="h-[18px] w-[18px] shrink-0"
            />
            <span className="flex-1 truncate text-sm font-medium">
              {showNode && "Update Ready"}
            </span>

            <Button
              variant="warning"
              size="iconMd"
              className="shrink-0 px-2.5 text-xs"
              onClick={handleUpdateCode}
              loading={loadingUpdate}
              data-testid="update-button"
            >
              Update
            </Button>
          </div>
        )}
        <div
          data-testid={`${data.id}-main-node`}
          className={cn(
            "grid gap-3 truncate text-wrap p-4 leading-5",
            showNode && "border-b",
          )}
        >
          <div
            data-testid={"div-generic-node"}
            className={
              !showNode
                ? ""
                : "generic-node-div-title justify-between rounded-t-lg"
            }
          >
            <div
              className={"generic-node-title-arrangement"}
              data-testid="generic-node-title-arrangement"
            >
              <NodeIcon
                dataType={data.type}
                showNode={showNode}
                icon={data.node?.icon}
                isGroup={!!data.node?.flow}
                hasToolMode={hasToolMode ?? false}
              />
              <div className="generic-node-tooltip-div">
                <NodeName
                  display_name={data.node?.display_name}
                  nodeId={data.id}
                  selected={selected}
                  showNode={showNode}
                  validationStatus={validationStatus}
                  isOutdated={isOutdated}
                  beta={data.node?.beta || false}
                />
              </div>
            </div>
            <div>
              {!showNode && (
                <>
                  <RenderInputParameters
                    data={data}
                    types={types}
                    isToolMode={isToolMode}
                    showNode={showNode}
                    shownOutputs={shownOutputs}
                    showHiddenOutputs={showHiddenOutputs}
                  />
                  {shownOutputs &&
                    shownOutputs.length > 0 &&
                    renderOutputs(shownOutputs)}
                </>
              )}
            </div>
            <NodeStatus
              data={data}
              frozen={data.node?.frozen}
              showNode={showNode}
              display_name={data.node?.display_name!}
              nodeId={data.id}
              selected={selected}
              setBorderColor={setBorderColor}
              buildStatus={buildStatus}
              isOutdated={isOutdated}
              isUserEdited={isUserEdited}
              getValidationStatus={getValidationStatus}
            />
          </div>
          {showNode && (
            <div>
              <NodeDescription
                description={data.node?.description}
                mdClassName={"dark:prose-invert"}
                nodeId={data.id}
                selected={selected}
              />
            </div>
          )}
        </div>
        {showNode && (
          <div className="relative">
            <>
              <RenderInputParameters
                data={data}
                types={types}
                isToolMode={isToolMode}
                showNode={showNode}
                shownOutputs={shownOutputs}
                showHiddenOutputs={showHiddenOutputs}
              />
              <div
                className={classNames(
                  Object.keys(data.node!.template).length < 1 ? "hidden" : "",
                  "flex-max-width justify-center",
                )}
              >
                {" "}
              </div>
              {!showHiddenOutputs &&
                shownOutputs &&
                shownOutputs.map((output, idx) => (
                  <OutputParameter
                    key={`shown-${output.name}-${idx}`}
                    output={output}
                    idx={
                      data.node!.outputs?.findIndex(
                        (out) => out.name === output.name,
                      ) ?? idx
                    }
                    lastOutput={idx === shownOutputs.length - 1}
                    data={data}
                    types={types}
                    selected={selected}
                    showNode={showNode}
                    isToolMode={isToolMode}
                  />
                ))}
              <div
                className={cn(showHiddenOutputs ? "" : "h-0 overflow-hidden")}
              >
                <div className="block">
                  {data.node!.outputs?.map((output, idx) => (
                    <OutputParameter
                      key={`hidden-${output.name}-${idx}`}
                      output={output}
                      idx={
                        data.node!.outputs?.findIndex(
                          (out) => out.name === output.name,
                        ) ?? idx
                      }
                      lastOutput={idx === (data.node!.outputs?.length ?? 0) - 1}
                      data={data}
                      types={types}
                      selected={selected}
                      showNode={showNode}
                      isToolMode={isToolMode}
                    />
                  ))}
                </div>
              </div>
              {hiddenOutputs && hiddenOutputs.length > 0 && (
                <ShadTooltip
                  content={
                    showHiddenOutputs
                      ? TOOLTIP_HIDDEN_OUTPUTS
                      : TOOLTIP_OPEN_HIDDEN_OUTPUTS
                  }
                >
                  <div
                    className={cn(
                      "absolute left-0 right-0 flex justify-center",
                      (shownOutputs && shownOutputs.length > 0) ||
                        showHiddenOutputs
                        ? "bottom-[-0.8rem]"
                        : "bottom-[-0.8rem]",
                    )}
                  >
                    <Button
                      unstyled
                      className="group flex h-6 w-6 items-center justify-center rounded-full border bg-background hover:border-foreground hover:text-foreground"
                      onClick={() => setShowHiddenOutputs(!showHiddenOutputs)}
                    >
                      <ForwardedIconComponent
                        name={showHiddenOutputs ? "EyeOff" : "Eye"}
                        strokeWidth={1.5}
                        className="h-4 w-4 text-placeholder-foreground group-hover:text-foreground"
                      />
                    </Button>
                  </div>
                </ShadTooltip>
              )}
            </>
          </div>
        )}
      </div>
    </div>
  );
}
