import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { BuildStatus } from "@/constants/enums";
import { usePostValidateComponentCode } from "@/controllers/API/queries/nodes/use-post-validate-component-code";
import { CustomNodeStatus } from "@/customization/components/custom-NodeStatus";
import UpdateComponentModal from "@/modals/updateComponentModal";
import { useAlternate } from "@/shared/hooks/use-alternate";
import { FlowStoreType } from "@/types/zustand/flow";
import { useUpdateNodeInternals } from "@xyflow/react";
import { cloneDeep } from "lodash";
import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { useShallow } from "zustand/react/shallow";
import { Button } from "../../components/ui/button";
import {
  ICON_STROKE_WIDTH,
  TOOLTIP_HIDDEN_OUTPUTS,
  TOOLTIP_OPEN_HIDDEN_OUTPUTS,
} from "../../constants/constants";
import NodeToolbarComponent from "../../pages/FlowPage/components/nodeToolbarComponent";
import { useChangeOnUnfocus } from "../../shared/hooks/use-change-on-unfocus";
import useAlertStore from "../../stores/alertStore";
import useFlowStore from "../../stores/flowStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { useShortcutsStore } from "../../stores/shortcuts";
import { useTypesStore } from "../../stores/typesStore";
import { OutputFieldType, VertexBuildTypeAPI } from "../../types/api";
import { NodeDataType } from "../../types/flow";
import { scapedJSONStringfy } from "../../utils/reactflowUtils";
import { classNames, cn } from "../../utils/utils";
import { processNodeAdvancedFields } from "../helpers/process-node-advanced-fields";
import useUpdateNodeCode from "../hooks/use-update-node-code";
import NodeDescription from "./components/NodeDescription";
import NodeName from "./components/NodeName";
import NodeOutputs from "./components/NodeOutputParameter/NodeOutputs";
import NodeUpdateComponent from "./components/NodeUpdateComponent";
import RenderInputParameters from "./components/RenderInputParameters";
import { NodeIcon } from "./components/nodeIcon";
import { useBuildStatus } from "./hooks/use-get-build-status";

const MemoizedRenderInputParameters = memo(RenderInputParameters);
const MemoizedNodeIcon = memo(NodeIcon);
const MemoizedNodeName = memo(NodeName);
const MemoizedNodeStatus = memo(CustomNodeStatus);
const MemoizedNodeDescription = memo(NodeDescription);
const MemoizedNodeOutputs = memo(NodeOutputs);

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
  const [borderColor, setBorderColor] = useState<string>("");
  const [loadingUpdate, setLoadingUpdate] = useState(false);
  const [showHiddenOutputs, setShowHiddenOutputs] = useState(false);
  const [validationStatus, setValidationStatus] =
    useState<VertexBuildTypeAPI | null>(null);
  const [openUpdateModal, setOpenUpdateModal] = useState(false);

  const types = useTypesStore((state) => state.types);
  const templates = useTypesStore((state) => state.templates);
  const deleteNode = useFlowStore((state) => state.deleteNode);
  const setNode = useFlowStore((state) => state.setNode);
  const updateNodeInternals = useUpdateNodeInternals();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
  const edges = useFlowStore((state) => state.edges);
  const setEdges = useFlowStore((state) => state.setEdges);
  const shortcuts = useShortcutsStore((state) => state.shortcuts);
  const buildStatus = useBuildStatus(data, data.id);
  const dismissedNodes = useFlowStore((state) => state.dismissedNodes);
  const addDismissedNodes = useFlowStore((state) => state.addDismissedNodes);
  const removeDismissedNodes = useFlowStore(
    (state) => state.removeDismissedNodes,
  );
  const dismissAll = useMemo(
    () => dismissedNodes.includes(data.id),
    [dismissedNodes, data.id],
  );

  const showNode = data.showNode ?? true;

  const getValidationStatus = useCallback((data) => {
    setValidationStatus(data);
    return null;
  }, []);

  const { mutate: validateComponentCode } = usePostValidateComponentCode();

  const [editNameDescription, toggleEditNameDescription, set] =
    useAlternate(false);

  const componentUpdate = useFlowStore(
    useShallow((state: FlowStoreType) =>
      state.componentsToUpdate.find((component) => component.id === data.id),
    ),
  );

  const {
    outdated: isOutdated,
    breakingChange: hasBreakingChange,
    userEdited: isUserEdited,
  } = componentUpdate ?? {
    outdated: false,
    breakingChange: false,
    userEdited: false,
  };

  const updateNodeCode = useUpdateNodeCode(
    data?.id,
    data.node!,
    setNode,
    updateNodeInternals,
  );

  useEffect(() => {
    updateNodeInternals(data.id);
  }, [data.node.template]);

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

  const handleUpdateCode = useCallback(
    (confirmed: boolean = false) => {
      if (!confirmed && hasBreakingChange) {
        setOpenUpdateModal(true);
        return;
      }
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
                removeDismissedNodes([data.id]);
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
    },
    [
      data,
      templates,
      hasBreakingChange,
      edges,
      updateNodeCode,
      validateComponentCode,
      setErrorData,
      takeSnapshot,
    ],
  );

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

  const { shownOutputs, hiddenOutputs } = useMemo(() => {
    const shownOutputs: typeof data.node.outputs = [];
    const hiddenOutputs: typeof data.node.outputs = [];
    (data.node?.outputs ?? []).forEach((output) => {
      if (output.hidden) {
        hiddenOutputs.push(output);
      } else {
        shownOutputs.push(output);
      }
    });
    return { shownOutputs, hiddenOutputs };
  }, [data.node?.outputs]);

  const [selectedOutput, setSelectedOutput] = useState<OutputFieldType | null>(
    null,
  );

  const handleSelectOutput = useCallback(
    (output) => {
      setSelectedOutput(output);
      // Remove any edges connected to this output handle
      const sourceHandleId = scapedJSONStringfy({
        output_types: [output.selected ?? output.types[0]],
        id: data.id,
        dataType: data.type,
        name: output.name,
      });

      setEdges((eds) =>
        eds.filter((edge) => edge.sourceHandle !== sourceHandleId),
      );

      setNode(data.id, (oldNode) => {
        const newNode = cloneDeep(oldNode);
        if (newNode.data.node?.outputs) {
          // First, clear any previous selections
          newNode.data.node.outputs.forEach((out) => {
            if (out.selected) {
              out.selected = undefined;
            }
          });

          // Then set the new selection
          const outputIndex = newNode.data.node.outputs.findIndex(
            (o) => o.name === output.name,
          );
          if (outputIndex !== -1) {
            const outputTypes = output.types || [];
            const defaultType =
              outputTypes.length > 0 ? outputTypes[0] : undefined;
            newNode.data.node.outputs[outputIndex].selected =
              output.selected ?? defaultType;
          }
        }
        return newNode;
      });
      updateNodeInternals(data.id);
    },
    [data.id, setNode, setEdges, updateNodeInternals],
  );

  const [hasChangedNodeDescription, setHasChangedNodeDescription] =
    useState(false);

  const editedNameDescription =
    editNameDescription && hasChangedNodeDescription;

  const hasDescription = useMemo(() => {
    return data.node?.description && data.node?.description !== "";
  }, [data.node?.description]);

  const selectedNodesCount = useMemo(() => {
    return useFlowStore.getState().nodes.filter((node) => node.selected).length;
  }, [selected]);

  const shouldShowUpdateComponent = useMemo(
    () => (isOutdated || hasBreakingChange) && !isUserEdited && !dismissAll,
    [isOutdated, hasBreakingChange, isUserEdited, dismissAll],
  );

  const memoizedNodeToolbarComponent = useMemo(() => {
    return selected && selectedNodesCount === 1 ? (
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
            updateNode={() => handleUpdateCode()}
            isOutdated={isOutdated && (dismissAll || isUserEdited)}
            isUserEdited={isUserEdited}
            hasBreakingChange={hasBreakingChange}
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
              editedNameDescription
                ? "bg-accent-emerald"
                : "bg-zinc-foreground",
            )}
            data-testid={
              editedNameDescription
                ? "save-name-description-button"
                : "edit-name-description-button"
            }
          >
            <ForwardedIconComponent
              name={editedNameDescription ? "Check" : "PencilLine"}
              strokeWidth={ICON_STROKE_WIDTH}
              className={cn(
                editedNameDescription
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
    selectedNodesCount,
  ]);
  useEffect(() => {
    if (hiddenOutputs && hiddenOutputs.length === 0) {
      setShowHiddenOutputs(false);
    }
  }, [hiddenOutputs]);

  const memoizedOnUpdateNode = useCallback(
    () => handleUpdateCode(true),
    [handleUpdateCode],
  );
  const memoizedSetDismissAll = useCallback(
    () => addDismissedNodes([data.id]),
    [addDismissedNodes, data.id],
  );

  return (
    <>
      {memoizedNodeToolbarComponent}
      {isOutdated && (data.node?.template?.code?.show ?? true) && (
        <NodeUpdateComponent
          isOutdated={isOutdated}
          loadingUpdate={loadingUpdate}
          handleUpdateCode={handleUpdateCode}
          hasBreakingChange={hasBreakingChange}
          openUpdateModal={openUpdateModal}
          setOpenUpdateModal={setOpenUpdateModal}
        />
      )}
      {(buildStatus || data.node?.beta) && (
        <MemoizedNodeStatus
          nodeId={data.id}
          display_name={data.node?.display_name ?? ""}
          selected={selected}
          setBorderColor={setBorderColor}
          frozen={data.node?.frozen}
          showNode={showNode}
          data={data}
          buildStatus={buildStatus}
          dismissAll={dismissAll}
          isOutdated={isOutdated}
          isUserEdited={isUserEdited}
          isBreakingChange={hasBreakingChange}
          getValidationStatus={getValidationStatus}
          beta={data.node?.beta ?? false}
        />
      )}

      <div
        className={cn(
          "generic-node-div",
          selected && "selected",
          !showNode && "hidden",
          data.node?.selected && "selected-node",
          buildStatus === BuildStatus.BUILDING && "animate-pulse",
        )}
        style={{
          borderColor: borderColor,
        }}
      >
        <div className="generic-node-div-header">
          <MemoizedNodeIcon data={data} />
          <MemoizedNodeName
            display_name={data.node?.display_name}
            nodeId={data.id}
            selected={selected}
            showNode={showNode}
            beta={data.node?.beta ?? false}
            editNameDescription={editNameDescription}
            toggleEditNameDescription={toggleEditNameDescription}
            setHasChangedNodeDescription={setHasChangedNodeDescription}
          />
          {data.node?.description &&
            (data.node.description.length > 0 || editNameDescription) && (
              <MemoizedNodeDescription
                description={data.node.description}
                selected={selected}
                nodeId={data.id}
                editNameDescription={editNameDescription}
                setEditNameDescription={set}
              />
            )}
        </div>

        <div className="generic-node-div-body">
          <MemoizedRenderInputParameters
            data={data}
            types={types}
            isToolMode={isToolMode}
            showNode={showNode}
            shownOutputs={shownOutputs}
            showHiddenOutputs={showHiddenOutputs}
          />
        </div>
        <div className="generic-node-div-footer">
          {data.node?.template &&
            Object.keys(data.node.template).length > 0 && (
              <div className="generic-node-menu-options">
                <MemoizedNodeOutputs
                  data={data}
                  selected={!!selected}
                  showNode={showNode}
                  isToolMode={isToolMode}
                  types={types}
                  outputs={shownOutputs}
                  showHiddenOutputs={showHiddenOutputs}
                  handleSelectOutput={handleSelectOutput}
                  keyPrefix="node-outputs"
                  selectedOutput={selectedOutput}
                />
                {Object.keys(data.node.template).some((e) =>
                  TOOLTIP_HIDDEN_OUTPUTS.includes(e),
                ) && (
                  <ShadTooltip
                    content={TOOLTIP_OPEN_HIDDEN_OUTPUTS}
                    side="bottom"
                  >
                    <HiddenOutputsButton
                      showHiddenOutputs={showHiddenOutputs}
                      onClick={() => setShowHiddenOutputs((prev) => !prev)}
                    />
                  </ShadTooltip>
                )}
              </div>
            )}
        </div>
      </div>
    </>
  );
}

export default memo(GenericNode);
