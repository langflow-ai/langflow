import { countHandlesFn } from "@/CustomNodes/helpers/count-handles";
import { mutateTemplate } from "@/CustomNodes/helpers/mutate-template";
import useHandleOnNewValue from "@/CustomNodes/hooks/use-handle-new-value";
import useHandleNodeClass from "@/CustomNodes/hooks/use-handle-node-class";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import ToggleShadComponent from "@/components/core/parameterRenderComponent/components/toggleShadComponent";
import { Button } from "@/components/ui/button";
import { usePatchUpdateFlow } from "@/controllers/API/queries/flows/use-patch-update-flow";
import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import { usePostRetrieveVertexOrder } from "@/controllers/API/queries/vertex";
import useAddFlow from "@/hooks/flows/use-add-flow";
import CodeAreaModal from "@/modals/codeAreaModal";
import { APIClassType } from "@/types/api";
import _, { cloneDeep } from "lodash";
import { useEffect, useRef, useState } from "react";
import { useUpdateNodeInternals } from "reactflow";
import IconComponent from "../../../../components/common/genericIconComponent";
import {
  Select,
  SelectContentWithoutPortal,
  SelectItem,
  SelectTrigger,
} from "../../../../components/ui/select-custom";
import ConfirmationModal from "../../../../modals/confirmationModal";
import EditNodeModal from "../../../../modals/editNodeModal";
import ShareModal from "../../../../modals/shareModal";
import useAlertStore from "../../../../stores/alertStore";
import { useDarkStore } from "../../../../stores/darkStore";
import useFlowStore from "../../../../stores/flowStore";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { useShortcutsStore } from "../../../../stores/shortcuts";
import { useStoreStore } from "../../../../stores/storeStore";
import { nodeToolbarPropsType } from "../../../../types/components";
import { FlowType } from "../../../../types/flow";
import {
  checkHasToolMode,
  createFlowComponent,
  downloadNode,
  expandGroupNode,
  updateFlowPosition,
} from "../../../../utils/reactflowUtils";
import { cn, getNodeLength, openInNewTab } from "../../../../utils/utils";
import useShortcuts from "./hooks/use-shortcuts";
import ShortcutDisplay from "./shortcutDisplay";
import ToolbarSelectItem from "./toolbarSelectItem";

export default function NodeToolbarComponent({
  data,
  deleteNode,
  setShowNode,
  numberOfOutputHandles,
  showNode,
  name = "code",
  onCloseAdvancedModal,
  updateNode,
  isOutdated,
  setOpenShowMoreOptions,
}: nodeToolbarPropsType): JSX.Element {
  const version = useDarkStore((state) => state.version);
  const [showModalAdvanced, setShowModalAdvanced] = useState(false);
  const [showconfirmShare, setShowconfirmShare] = useState(false);
  const [showOverrideModal, setShowOverrideModal] = useState(false);
  const [flowComponent, setFlowComponent] = useState<FlowType>(
    createFlowComponent(cloneDeep(data), version),
  );
  const nodeLength = getNodeLength(data);
  const updateFreezeStatus = useFlowStore((state) => state.updateFreezeStatus);
  const hasStore = useStoreStore((state) => state.hasStore);
  const hasApiKey = useStoreStore((state) => state.hasApiKey);
  const validApiKey = useStoreStore((state) => state.validApiKey);
  const shortcuts = useShortcutsStore((state) => state.shortcuts);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const [openModal, setOpenModal] = useState(false);
  const isGroup = data.node?.flow ? true : false;
  const frozen = data.node?.frozen ?? false;
  const currentFlow = useFlowStore((state) => state.currentFlow);

  const addFlow = useAddFlow();

  const { mutate: patchUpdateFlow } = usePatchUpdateFlow();

  const isMinimal = countHandlesFn(data) <= 1 && numberOfOutputHandles <= 1;
  function activateToolMode() {
    const newValue = !toolMode;
    setToolMode(newValue);

    updateToolMode(data.id, newValue);
    data.node!.tool_mode = newValue;

    mutateTemplate(
      newValue,
      data.node!,
      handleNodeClass,
      postToolModeValue,
      setErrorData,
      "tool_mode",
      () => {
        const node = currentFlow?.data?.nodes.find(
          (node) => node.id === data.id,
        );
        const index = currentFlow?.data?.nodes.indexOf(node!)!;
        currentFlow!.data!.nodes[index]!.data.node.tool_mode = newValue;

        patchUpdateFlow({
          id: currentFlow?.id!,
          name: currentFlow?.name!,
          data: currentFlow?.data!,
          description: currentFlow?.description!,
          folder_id: currentFlow?.folder_id!,
          endpoint_name: currentFlow?.endpoint_name!,
        });
      },
    );

    updateNodeInternals(data.id);
  }
  function minimize() {
    if (isMinimal || !showNode) {
      setShowNode((data.showNode ?? true) ? false : true);
      updateNodeInternals(data.id);
      return;
    }
    setNoticeData({
      title:
        "Minimization are only available for components with one handle or fewer.",
    });
    return;
  }

  function handleungroup() {
    if (isGroup) {
      takeSnapshot();
      expandGroupNode(
        data.id,
        updateFlowPosition(getNodePosition(data.id), data.node?.flow!),
        data.node!.template,
        nodes,
        edges,
        setNodes,
        setEdges,
        data.node?.outputs,
      );
    }
  }

  function shareComponent() {
    if (hasApiKey || hasStore) {
      setShowconfirmShare((state) => !state);
    }
  }

  function handleCodeModal() {
    if (!hasCode)
      setNoticeData({ title: `You can not access ${data.id} code` });
    setOpenModal((state) => !state);
  }

  function saveComponent() {
    if (isSaved) {
      setShowOverrideModal((state) => !state);
      return;
    }
    addFlow({
      flow: flowComponent,
      override: false,
    });
    setSuccessData({ title: `${data.id} saved successfully` });
    return;
  }
  // Check if any of the data.node.template fields have tool_mode as True
  // if so we can show the tool mode button
  const hasToolMode = checkHasToolMode(data.node?.template ?? {});

  function openDocs() {
    if (data.node?.documentation) {
      return openInNewTab(data.node?.documentation);
    }
    setNoticeData({
      title: `${data.id} docs is not available at the moment.`,
    });
  }

  const freezeFunction = () => {
    setNode(data.id, (old) => ({
      ...old,
      data: {
        ...old.data,
        node: {
          ...old.data.node,
          frozen: old.data?.node?.frozen ? false : true,
        },
      },
    }));
  };

  useShortcuts({
    showOverrideModal,
    showModalAdvanced,
    openModal,
    showconfirmShare,
    FreezeAllVertices: () => {
      FreezeAllVertices({ flowId: currentFlowId, stopNodeId: data.id });
    },
    Freeze: freezeFunction,
    downloadFunction: () => downloadNode(flowComponent!),
    displayDocs: openDocs,
    saveComponent,
    showAdvance: () => setShowModalAdvanced((state) => !state),
    handleCodeModal,
    shareComponent,
    ungroup: handleungroup,
    minimizeFunction: minimize,
    activateToolMode: activateToolMode,
    hasToolMode,
  });

  const paste = useFlowStore((state) => state.paste);
  const nodes = useFlowStore((state) => state.nodes);
  const edges = useFlowStore((state) => state.edges);
  const setNodes = useFlowStore((state) => state.setNodes);
  const setEdges = useFlowStore((state) => state.setEdges);
  const getNodePosition = useFlowStore((state) => state.getNodePosition);
  const flows = useFlowsManagerStore((state) => state.flows);
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
  const { mutate: FreezeAllVertices } = usePostRetrieveVertexOrder({
    onSuccess: ({ vertices_to_run }) => {
      updateFreezeStatus(vertices_to_run, !data.node?.frozen);
      vertices_to_run.forEach((vertex) => {
        updateNodeInternals(vertex);
      });
    },
  });
  const updateToolMode = useFlowStore((state) => state.updateToolMode);

  useEffect(() => {
    if (!showModalAdvanced) {
      onCloseAdvancedModal!(false);
    }
  }, [showModalAdvanced]);
  const updateNodeInternals = useUpdateNodeInternals();

  const setLastCopiedSelection = useFlowStore(
    (state) => state.setLastCopiedSelection,
  );

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setNoticeData = useAlertStore((state) => state.setNoticeData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  useEffect(() => {
    setFlowComponent(createFlowComponent(cloneDeep(data), version));
  }, [
    data,
    data.node,
    data.node?.display_name,
    data.node?.description,
    data.node?.template,
    showModalAdvanced,
    showconfirmShare,
  ]);

  const [selectedValue, setSelectedValue] = useState(null);

  const handleSelectChange = (event) => {
    setSelectedValue(event);

    switch (event) {
      case "save":
        saveComponent();
        break;
      case "freeze":
        freezeFunction();
        break;
      case "freezeAll":
        FreezeAllVertices({ flowId: currentFlowId, stopNodeId: data.id });
        break;
      case "code":
        setOpenModal(!openModal);
        break;
      case "advanced":
        setShowModalAdvanced(true);
        break;
      case "show":
        takeSnapshot();
        minimize();
        break;
      case "Share":
        shareComponent();
        break;
      case "Download":
        downloadNode(flowComponent!);
        break;
      case "SaveAll":
        addFlow({
          flow: flowComponent,
          override: false,
        });
        break;
      case "documentation":
        openDocs();
        break;
      case "disabled":
        break;
      case "ungroup":
        handleungroup();
        break;
      case "override":
        setShowOverrideModal(true);
        break;
      case "delete":
        deleteNode(data.id);
        break;
      case "update":
        updateNode();
        break;
      case "copy":
        const node = nodes.filter((node) => node.id === data.id);
        setLastCopiedSelection({ nodes: _.cloneDeep(node), edges: [] });
        break;
      case "duplicate":
        paste(
          {
            nodes: [nodes.find((node) => node.id === data.id)!],
            edges: [],
          },
          {
            x: 50,
            y: 10,
            paneX: nodes.find((node) => node.id === data.id)?.position.x,
            paneY: nodes.find((node) => node.id === data.id)?.position.y,
          },
        );
        break;
      case "toolMode":
        activateToolMode();
        break;
    }

    setSelectedValue(null);
  };

  const isSaved = flows?.some((flow) =>
    Object.values(flow).includes(data.node?.display_name!),
  );

  const setNode = useFlowStore((state) => state.setNode);

  const { handleOnNewValue: handleOnNewValueHook } = useHandleOnNewValue({
    node: data.node!,
    nodeId: data.id,
    name,
  });

  const handleOnNewValue = (value: string | string[]) => {
    handleOnNewValueHook({ value });
  };

  const { handleNodeClass: handleNodeClassHook } = useHandleNodeClass(data.id);

  const handleNodeClass = (newNodeClass: APIClassType, type: string) => {
    handleNodeClassHook(newNodeClass, type);
  };

  const hasCode = Object.keys(data.node!.template).includes("code");

  const selectTriggerRef = useRef(null);

  const handleButtonClick = () => {
    (selectTriggerRef.current! as HTMLElement)?.click();
  };

  const handleOpenChange = (open: boolean) => {
    setOpenShowMoreOptions && setOpenShowMoreOptions(open);
  };

  const [toolMode, setToolMode] = useState(() => {
    // Check if tool mode is explicitly set on the node
    const hasToolModeProperty = data.node?.tool_mode;
    if (hasToolModeProperty) {
      return hasToolModeProperty;
    }

    // Otherwise check if node has component_as_tool output
    const hasComponentAsTool = data.node?.outputs?.some(
      (output) => output.name === "component_as_tool",
    );

    return hasComponentAsTool ?? false;
  });

  const postToolModeValue = usePostTemplateValue({
    node: data.node!,
    nodeId: data.id,
    parameterId: "tool_mode",
    tool_mode: data.node!.tool_mode ?? false,
  });

  return (
    <>
      <div className="noflow nopan nodelete nodrag">
        <div className="toolbar-wrapper">
          {hasCode && (
            <ShadTooltip
              content={
                <ShortcutDisplay
                  {...shortcuts.find(
                    ({ name }) => name.split(" ")[0].toLowerCase() === "code",
                  )!}
                />
              }
              side="top"
            >
              <Button
                className="node-toolbar-buttons"
                variant="ghost"
                onClick={() => {
                  setOpenModal(!openModal);
                }}
                data-testid="code-button-modal"
                size="node-toolbar"
              >
                <IconComponent name="Code" className="h-4 w-4" />

                <span className="text-[13px] font-medium">Code</span>
              </Button>
            </ShadTooltip>
          )}

          {nodeLength > 0 && (
            <ShadTooltip
              content={
                <ShortcutDisplay
                  {...shortcuts.find(
                    ({ name }) =>
                      name.split(" ")[0].toLowerCase() === "advanced",
                  )!}
                />
              }
              side="top"
            >
              <Button
                className="node-toolbar-buttons"
                variant="ghost"
                onClick={() => {
                  setShowModalAdvanced(true);
                }}
                data-testid="edit-button-modal"
                size="node-toolbar"
              >
                <IconComponent name="SlidersHorizontal" className="h-4 w-4" />
                <span className="text-[13px] font-medium">Controls</span>
              </Button>
            </ShadTooltip>
          )}
          {!hasToolMode && (
            <ShadTooltip
              content={
                <ShortcutDisplay
                  {...shortcuts.find(
                    ({ name }) => name.toLowerCase() === "freeze path",
                  )!}
                />
              }
              side="top"
            >
              <Button
                className={cn(
                  "node-toolbar-buttons",
                  frozen && "text-blue-500",
                )}
                variant="ghost"
                onClick={(event) => {
                  event.preventDefault();
                  takeSnapshot();
                  FreezeAllVertices({
                    flowId: currentFlowId,
                    stopNodeId: data.id,
                  });
                }}
                size="node-toolbar"
              >
                <IconComponent
                  name="FreezeAll"
                  className={cn(
                    "h-4 w-4 transition-all",
                    frozen ? "animate-wiggle text-ice" : "",
                  )}
                />
                <span className="text-[13px] font-medium">Freeze Path</span>
              </Button>
            </ShadTooltip>
          )}
          {hasToolMode && (
            <ShadTooltip
              content={
                <ShortcutDisplay
                  {...shortcuts.find(
                    ({ name }) => name.toLowerCase() === "tool mode",
                  )!}
                />
              }
              side="top"
            >
              <Button
                className={cn(
                  "node-toolbar-buttons h-[2rem]",
                  toolMode && "text-primary",
                )}
                variant="ghost"
                onClick={(event) => {
                  event.preventDefault();
                  takeSnapshot();
                  handleSelectChange("toolMode");
                }}
                size="node-toolbar"
              >
                <IconComponent
                  name="Hammer"
                  className={cn(
                    "h-4 w-4 transition-all",
                    toolMode ? "text-primary" : "",
                  )}
                />
                <span className="text-[13px] font-medium">Tool Mode</span>
                <ToggleShadComponent
                  value={toolMode}
                  editNode={false}
                  handleOnNewValue={() => {}}
                  disabled={false}
                  size="medium"
                  showToogle={false}
                  id="tool-mode-toggle"
                />
              </Button>
            </ShadTooltip>
          )}

          <Select
            onValueChange={handleSelectChange}
            value={selectedValue!}
            onOpenChange={handleOpenChange}
          >
            <SelectTrigger className="w-62">
              <ShadTooltip content="Show More" side="top">
                <div>
                  <Button
                    className="node-toolbar-buttons h-[2rem] w-[2rem]"
                    variant="ghost"
                    onClick={handleButtonClick}
                    size="node-toolbar"
                    data-testid="more-options-modal"
                  >
                    <IconComponent name="MoreHorizontal" className="h-4 w-4" />
                  </Button>
                </div>
              </ShadTooltip>
            </SelectTrigger>
            <SelectContentWithoutPortal
              className={"relative top-1 w-56 bg-background"}
            >
              {hasCode && (
                <SelectItem value={"code"}>
                  <ToolbarSelectItem
                    shortcut={
                      shortcuts.find((obj) => obj.name === "Code")?.shortcut!
                    }
                    value={"Code"}
                    icon={"Code"}
                    dataTestId="code-button-modal"
                  />
                </SelectItem>
              )}
              {nodeLength > 0 && (
                <SelectItem value={nodeLength === 0 ? "disabled" : "advanced"}>
                  <ToolbarSelectItem
                    shortcut={
                      shortcuts.find((obj) => obj.name === "Advanced Settings")
                        ?.shortcut!
                    }
                    value={"Controls"}
                    icon={"SlidersHorizontal"}
                    dataTestId="advanced-button-modal"
                  />
                </SelectItem>
              )}
              <SelectItem value={"save"}>
                <ToolbarSelectItem
                  shortcut={
                    shortcuts.find((obj) => obj.name === "Save Component")
                      ?.shortcut!
                  }
                  value={"Save"}
                  icon={"SaveAll"}
                  dataTestId="save-button-modal"
                />
              </SelectItem>
              <SelectItem value={"duplicate"}>
                <ToolbarSelectItem
                  shortcut={
                    shortcuts.find((obj) => obj.name === "Duplicate")?.shortcut!
                  }
                  value={"Duplicate"}
                  icon={"Copy"}
                  dataTestId="copy-button-modal"
                />
              </SelectItem>
              <SelectItem value={"copy"}>
                <ToolbarSelectItem
                  shortcut={
                    shortcuts.find((obj) => obj.name === "Copy")?.shortcut!
                  }
                  value={"Copy"}
                  icon={"Clipboard"}
                  dataTestId="copy-button-modal"
                />
              </SelectItem>
              {isOutdated && (
                <SelectItem value={"update"}>
                  <ToolbarSelectItem
                    shortcut={
                      shortcuts.find((obj) => obj.name === "Update")?.shortcut!
                    }
                    value={"Restore"}
                    icon={"RefreshCcwDot"}
                    dataTestId="update-button-modal"
                  />
                </SelectItem>
              )}
              {hasStore && (
                <SelectItem
                  value={"Share"}
                  disabled={!hasApiKey || !validApiKey}
                >
                  <ToolbarSelectItem
                    shortcut={
                      shortcuts.find((obj) => obj.name === "Component Share")
                        ?.shortcut!
                    }
                    value={"Share"}
                    icon={"Share3"}
                    dataTestId="share-button-modal"
                  />
                </SelectItem>
              )}

              <SelectItem
                value={"documentation"}
                disabled={data.node?.documentation === ""}
              >
                <ToolbarSelectItem
                  shortcut={
                    shortcuts.find((obj) => obj.name === "Docs")?.shortcut!
                  }
                  value={"Docs"}
                  icon={"FileText"}
                  dataTestId="docs-button-modal"
                />
              </SelectItem>
              {(isMinimal || !showNode) && (
                <SelectItem
                  value={"show"}
                  data-testid={`${showNode ? "minimize" : "expand"}-button-modal`}
                >
                  <ToolbarSelectItem
                    shortcut={
                      shortcuts.find((obj) => obj.name === "Minimize")
                        ?.shortcut!
                    }
                    value={showNode ? "Minimize" : "Expand"}
                    icon={showNode ? "Minimize2" : "Maximize2"}
                    dataTestId="minimize-button-modal"
                  />
                </SelectItem>
              )}
              {isGroup && (
                <SelectItem value="ungroup">
                  <ToolbarSelectItem
                    shortcut={
                      shortcuts.find((obj) => obj.name === "Group")?.shortcut!
                    }
                    value={"Ungroup"}
                    icon={"Ungroup"}
                    dataTestId="group-button-modal"
                  />
                </SelectItem>
              )}
              <SelectItem value="freeze">
                <ToolbarSelectItem
                  shortcut={
                    shortcuts.find((obj) => obj.name === "Freeze")?.shortcut!
                  }
                  value={"Freeze"}
                  icon={"Snowflake"}
                  dataTestId="freeze-button"
                  style={`${frozen ? " text-ice" : ""} transition-all`}
                />
              </SelectItem>
              <SelectItem value="freezeAll">
                <ToolbarSelectItem
                  shortcut={
                    shortcuts.find((obj) => obj.name === "Freeze Path")
                      ?.shortcut!
                  }
                  value={"Freeze Path"}
                  icon={"FreezeAll"}
                  dataTestId="freeze-path-button"
                  style={`${frozen ? " text-ice" : ""} transition-all`}
                />
              </SelectItem>
              <SelectItem value="Download">
                <ToolbarSelectItem
                  shortcut={
                    shortcuts.find((obj) => obj.name === "Download")?.shortcut!
                  }
                  value={"Download"}
                  icon={"Download"}
                  dataTestId="download-button-modal"
                />
              </SelectItem>
              <SelectItem value={"delete"} className="focus:bg-red-400/[.20]">
                <div className="font-red flex text-status-red">
                  <IconComponent
                    name="Trash2"
                    className="relative top-0.5 mr-2 h-4 w-4"
                  />{" "}
                  <span className="">Delete</span>{" "}
                  <span
                    className={`absolute right-2 top-2 flex items-center justify-center rounded-sm px-1 py-[0.2]`}
                  >
                    <IconComponent
                      name="Delete"
                      className="h-4 w-4 stroke-2 text-red-400"
                    ></IconComponent>
                  </span>
                </div>
              </SelectItem>
              {hasToolMode && (
                <SelectItem value="toolMode">
                  <ToolbarSelectItem
                    shortcut={
                      shortcuts.find((obj) => obj.name === "Tool Mode")
                        ?.shortcut!
                    }
                    value={"Tool Mode"}
                    icon={"Hammer"}
                    dataTestId="tool-mode-button"
                    style={`${toolMode ? "text-primary" : ""} transition-all`}
                  />
                </SelectItem>
              )}
            </SelectContentWithoutPortal>
          </Select>
        </div>

        <ConfirmationModal
          open={showOverrideModal}
          title={`Replace`}
          cancelText="Create New"
          confirmationText="Replace"
          size={"x-small"}
          icon={"SaveAll"}
          index={6}
          onConfirm={() => {
            addFlow({
              flow: flowComponent,
              override: true,
            });
            setSuccessData({ title: `${data.id} successfully overridden!` });
            setShowOverrideModal(false);
          }}
          onClose={() => setShowOverrideModal(false)}
          onCancel={() => {
            addFlow({
              flow: flowComponent,
              override: true,
            });
            setSuccessData({ title: "New component successfully saved!" });
            setShowOverrideModal(false);
          }}
        >
          <ConfirmationModal.Content>
            <span>
              It seems {data.node?.display_name} already exists. Do you want to
              replace it with the current or create a new one?
            </span>
          </ConfirmationModal.Content>
        </ConfirmationModal>
        {showModalAdvanced && (
          <EditNodeModal
            data={data}
            open={showModalAdvanced}
            setOpen={setShowModalAdvanced}
          />
        )}
        {showconfirmShare && (
          <ShareModal
            open={showconfirmShare}
            setOpen={setShowconfirmShare}
            is_component={true}
            component={flowComponent!}
          />
        )}
        {hasCode && (
          <div className="hidden">
            {openModal && (
              <CodeAreaModal
                setValue={handleOnNewValue}
                open={openModal}
                setOpen={setOpenModal}
                dynamic={true}
                setNodeClass={(apiClassType, type) => {
                  handleNodeClass(apiClassType, type);
                  setToolMode(false);
                }}
                nodeClass={data.node}
                value={data.node?.template[name].value ?? ""}
                componentId={data.id}
              >
                <></>
              </CodeAreaModal>
            )}
          </div>
        )}
      </div>
    </>
  );
}
