import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { usePostValidateComponentCode } from "@/controllers/API/queries/nodes/use-post-validate-component-code";
import { useUpdateNodeInternals } from "@xyflow/react";
import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { Button } from "../../components/ui/button";
import {
  ICON_STROKE_WIDTH,
  TOOLTIP_HIDDEN_OUTPUTS,
  TOOLTIP_OPEN_HIDDEN_OUTPUTS,
} from "../../constants/constants";
import NodeToolbarComponent from "../../pages/FlowPage/components/nodeToolbarComponent";
import useAlertStore from "../../stores/alertStore";
import useFlowStore from "../../stores/flowStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { useShortcutsStore } from "../../stores/shortcuts";
import { useTypesStore } from "../../stores/typesStore";
import { VertexBuildTypeAPI } from "../../types/api";
import { NodeDataType } from "../../types/flow";
import { checkHasToolMode } from "../../utils/reactflowUtils";
import { classNames, cn } from "../../utils/utils";

import { useAlternate } from "@/shared/hooks/use-alternate";
import { useUtilityStore } from "@/stores/utilityStore";
import { useChangeOnUnfocus } from "../../shared/hooks/use-change-on-unfocus";
import { processNodeAdvancedFields } from "../helpers/process-node-advanced-fields";
import useCheckCodeValidity from "../hooks/use-check-code-validity";
import useUpdateNodeCode from "../hooks/use-update-node-code";
import NodeDescription from "./components/NodeDescription";
import NodeName from "./components/NodeName";
import { OutputParameter } from "./components/NodeOutputParameter";
import NodeStatus from "./components/NodeStatus";
import RenderInputParameters from "./components/RenderInputParameters";
import { NodeIcon } from "./components/nodeIcon";
import { useBuildStatus } from "./hooks/use-get-build-status";

const MemoizedOutputParameter = memo(OutputParameter);
const MemoizedRenderInputParameters = memo(RenderInputParameters);
const MemoizedNodeIcon = memo(NodeIcon);
const MemoizedNodeName = memo(NodeName);
const MemoizedNodeStatus = memo(NodeStatus);
const MemoizedNodeDescription = memo(NodeDescription);

const HiddenOutputsButton = memo(
  ({
    showHiddenOutputs,
    onClick,
  }: {
    showHiddenOutputs: boolean;
    onClick: () => void;
  }) => (
    <Button
      unstyled
      className="group flex h-[1.75rem] w-[1.75rem] items-center justify-center rounded-full border bg-muted hover:text-foreground"
      onClick={onClick}
    >
      <ForwardedIconComponent
        name={showHiddenOutputs ? "ChevronsDownUp" : "ChevronsUpDown"}
        strokeWidth={ICON_STROKE_WIDTH}
        className="icon-size text-placeholder-foreground group-hover:text-foreground"
      />
    </Button>
  ),
);

function GenericNode({
  data,
  selected,
}: {
  data: NodeDataType;
  selected?: boolean;
  xPos?: number;
  yPos?: number;
}): JSX.Element {
  const [isOutdated, setIsOutdated] = useState(false);
  const [isUserEdited, setIsUserEdited] = useState(false);
  const [borderColor, setBorderColor] = useState<string>("");
  const [loadingUpdate, setLoadingUpdate] = useState(false);
  const [showHiddenOutputs, setShowHiddenOutputs] = useState(false);
  const [validationStatus, setValidationStatus] =
    useState<VertexBuildTypeAPI | null>(null);

  const types = useTypesStore((state) => state.types);
  const templates = useTypesStore((state) => state.templates);
  const deleteNode = useFlowStore((state) => state.deleteNode);
  const setNode = useFlowStore((state) => state.setNode);
  const updateNodeInternals = useUpdateNodeInternals();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
  const edges = useFlowStore((state) => state.edges);
  const shortcuts = useShortcutsStore((state) => state.shortcuts);
  const buildStatus = useBuildStatus(data, data.id);
  const dismissAll = useUtilityStore((state) => state.dismissAll);

  const showNode = data.showNode ?? true;

  const getValidationStatus = (data) => {
    setValidationStatus(data);
    return null;
  };

  const { mutate: validateComponentCode } = usePostValidateComponentCode();

  const [editNameDescription, toggleEditNameDescription, set] =
    useAlternate(false);

  const updateNodeCode = useUpdateNodeCode(
    data?.id,
    data.node!,
    setNode,
    setIsOutdated,
    setIsUserEdited,
    updateNodeInternals,
  );

  useCheckCodeValidity(data, templates, setIsOutdated, setIsUserEdited, types);

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

  const handleUpdateCode = useCallback(() => {
    setLoadingUpdate(true);
    takeSnapshot();

    const thisNodeTemplate = templates[data.type]?.template;
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
              title: "Error updating Component code",
              list: [
                "There was an error updating the Component.",
                "If the error persists, please report it on our Discord or GitHub.",
              ],
            });
            console.error(error);
            setLoadingUpdate(false);
          },
        },
      );
    }
  }, [
    data,
    templates,
    edges,
    updateNodeCode,
    validateComponentCode,
    setErrorData,
    takeSnapshot,
  ]);

  const handleUpdateCodeWShortcut = useCallback(() => {
    if (isOutdated && selected) {
      handleUpdateCode();
    }
  }, [isOutdated, selected, handleUpdateCode]);

  const update = useShortcutsStore((state) => state.update);
  useHotkeys(update, handleUpdateCodeWShortcut, { preventDefault: true });

  // Memoized values
  const isToolMode = useMemo(
    () =>
      data.node?.outputs?.some(
        (output) => output.name === "component_as_tool",
      ) ??
      data.node?.tool_mode ??
      false,
    [data.node?.outputs, data.node?.tool_mode],
  );

  const hasToolMode = useMemo(
    () => checkHasToolMode(data.node?.template ?? {}),
    [data.node?.template],
  );

  const hasOutputs = useMemo(
    () => data.node?.outputs && data.node.outputs.length > 0,
    [data.node?.outputs],
  );

  const nodeRef = useRef<HTMLDivElement>(null);

  useChangeOnUnfocus({
    selected,
    value: editNameDescription,
    onChange: set,
    defaultValue: false,
    shouldChangeValue: (value) => value === true,
    nodeRef,
    callback: toggleEditNameDescription,
  });

  const renderOutputs = useCallback(
    (outputs, key?: string) => {
      return outputs?.map((output, idx) => (
        <MemoizedOutputParameter
          key={`${key}-${output.name}-${idx}`}
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
    },
    [data, types, selected, showNode, isToolMode],
  );

  const { shownOutputs, hiddenOutputs } = useMemo(
    () => ({
      shownOutputs:
        data.node?.outputs?.filter((output) => !output.hidden) ?? [],
      hiddenOutputs:
        data.node?.outputs?.filter((output) => output.hidden) ?? [],
    }),
    [data.node?.outputs],
  );

  const [hasChangedNodeDescription, setHasChangedNodeDescription] =
    useState(false);

  const memoizedNodeToolbarComponent = useMemo(() => {
    return selected ? (
      <>
        <div
          className={cn(
            "absolute -top-12 left-1/2 z-50 -translate-x-1/2",
            "transform transition-all duration-300 ease-out",
          )}
        >
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
          />
        </div>
        <div className="-z-10">
          <Button
            unstyled
            onClick={() => {
              toggleEditNameDescription();
              setHasChangedNodeDescription(false);
            }}
            className={cn(
              "nodrag absolute left-1/2 z-50 flex h-6 w-6 cursor-pointer items-center justify-center rounded-md",
              "transform transition-all duration-300 ease-out",
              showNode
                ? "top-2 translate-x-[10.4rem]"
                : "top-0 translate-x-[6.4rem]",
              editNameDescription && hasChangedNodeDescription
                ? "bg-accent-emerald"
                : "bg-zinc-foreground",
            )}
            data-testid={
              editNameDescription && hasChangedNodeDescription
                ? "save-name-description-button"
                : "edit-name-description-button"
            }
          >
            <ForwardedIconComponent
              name={
                editNameDescription && hasChangedNodeDescription
                  ? "Check"
                  : "PencilLine"
              }
              strokeWidth={ICON_STROKE_WIDTH}
              className={cn(
                editNameDescription && hasChangedNodeDescription
                  ? "text-accent-emerald-foreground"
                  : "text-muted-foreground",
                "icon-size",
              )}
            />
          </Button>
        </div>
      </>
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
    editNameDescription,
    hasChangedNodeDescription,
    toggleEditNameDescription,
  ]);

  useEffect(() => {
    if (hiddenOutputs && hiddenOutputs.length === 0) {
      setShowHiddenOutputs(false);
    }
  }, [hiddenOutputs]);

  const renderNodeIcon = useCallback(() => {
    return (
      <MemoizedNodeIcon
        dataType={data.type}
        showNode={showNode}
        icon={data.node?.icon}
        isGroup={!!data.node?.flow}
        hasToolMode={hasToolMode ?? false}
      />
    );
  }, [data.type, showNode, data.node?.icon, data.node?.flow, hasToolMode]);

  const renderNodeName = useCallback(() => {
    return (
      <MemoizedNodeName
        display_name={data.node?.display_name}
        nodeId={data.id}
        selected={selected}
        showNode={showNode}
        validationStatus={validationStatus}
        isOutdated={isOutdated}
        beta={data.node?.beta || false}
        editNameDescription={editNameDescription}
        toggleEditNameDescription={toggleEditNameDescription}
        setHasChangedNodeDescription={setHasChangedNodeDescription}
      />
    );
  }, [
    data.node?.display_name,
    data.id,
    selected,
    showNode,
    validationStatus,
    isOutdated,
    data.node?.beta,
    editNameDescription,
    toggleEditNameDescription,
    setHasChangedNodeDescription,
  ]);

  const renderNodeStatus = useCallback(() => {
    return (
      <MemoizedNodeStatus
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
        handleUpdateComponent={handleUpdateCode}
      />
    );
  }, [
    data,
    showNode,
    selected,
    buildStatus,
    isOutdated,
    isUserEdited,
    getValidationStatus,
    dismissAll,
    handleUpdateCode,
  ]);

  const renderDescription = useCallback(() => {
    return (
      <MemoizedNodeDescription
        description={data.node?.description}
        mdClassName={"dark:prose-invert"}
        nodeId={data.id}
        selected={selected}
        editNameDescription={editNameDescription}
        setEditNameDescription={set}
        setHasChangedNodeDescription={setHasChangedNodeDescription}
      />
    );
  }, [
    data.node?.description,
    data.id,
    selected,
    editNameDescription,
    toggleEditNameDescription,
    setHasChangedNodeDescription,
  ]);

  const renderInputParameters = useCallback(() => {
    return (
      <MemoizedRenderInputParameters
        data={data}
        types={types}
        isToolMode={isToolMode}
        showNode={showNode}
        shownOutputs={shownOutputs}
        showHiddenOutputs={showHiddenOutputs}
      />
    );
  }, [data, types, isToolMode, showNode, shownOutputs, showHiddenOutputs]);

  return (
    <div
      className={cn(
        isOutdated && !isUserEdited && !dismissAll ? "relative -mt-10" : "",
      )}
    >
      <div
        className={cn(
          borderColor,
          showNode ? "w-80" : `w-48`,
          "generic-node-div group/node relative rounded-xl shadow-sm hover:shadow-md",
          !hasOutputs && "pb-4",
        )}
      >
        {memoizedNodeToolbarComponent}
        {isOutdated && !isUserEdited && !dismissAll && (
          <div className="flex h-10 w-full items-center gap-4 rounded-t-[0.69rem] bg-warning p-2 px-4 text-warning-foreground">
            <ForwardedIconComponent
              name="AlertTriangle"
              strokeWidth={ICON_STROKE_WIDTH}
              className="icon-size shrink-0"
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
            "grid gap-3 text-wrap p-4 leading-5",
            showNode ? "border-b" : "relative",
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
              {renderNodeIcon()}
              <div className="generic-node-tooltip-div truncate">
                {renderNodeName()}
              </div>
            </div>
            <div data-testid={`${showNode ? "show" : "hide"}-node-content`}>
              {!showNode && (
                <>
                  {renderInputParameters()}
                  {shownOutputs &&
                    shownOutputs.length > 0 &&
                    renderOutputs(shownOutputs, "render-outputs")}
                </>
              )}
            </div>
            {renderNodeStatus()}
          </div>
          {showNode && <div>{renderDescription()}</div>}
        </div>
        {showNode && (
          <div className="nopan nodelete nodrag noflow relative cursor-auto">
            <>
              {renderInputParameters()}
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
                renderOutputs(shownOutputs, "shown")}

              <div
                className={cn(showHiddenOutputs ? "" : "h-0 overflow-hidden")}
              >
                <div className="block">
                  {renderOutputs(data.node!.outputs, "hidden")}
                </div>
              </div>
              {hiddenOutputs && hiddenOutputs.length > 0 && (
                <ShadTooltip
                  content={
                    showHiddenOutputs
                      ? `${TOOLTIP_HIDDEN_OUTPUTS} (${hiddenOutputs?.length})`
                      : `${TOOLTIP_OPEN_HIDDEN_OUTPUTS} (${hiddenOutputs?.length})`
                  }
                >
                  <div
                    className={cn(
                      "absolute left-1/2 flex -translate-x-1/2 justify-center",
                      (shownOutputs && shownOutputs.length > 0) ||
                        showHiddenOutputs
                        ? "bottom-[-0.8rem]"
                        : "bottom-[-0.8rem]",
                    )}
                  >
                    <HiddenOutputsButton
                      showHiddenOutputs={showHiddenOutputs}
                      onClick={() => setShowHiddenOutputs(!showHiddenOutputs)}
                    />
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

export default memo(GenericNode);
