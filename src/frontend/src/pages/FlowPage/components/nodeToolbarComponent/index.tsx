import _, { cloneDeep } from "lodash";
import { useEffect, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { useUpdateNodeInternals } from "reactflow";
import CodeAreaComponent from "../../../../components/codeAreaComponent";
import IconComponent from "../../../../components/genericIconComponent";
import RenderIcons from "../../../../components/renderIconComponent";
import ShadTooltip from "../../../../components/shadTooltipComponent";
import {
  Select,
  SelectContent,
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
import { APIClassType } from "../../../../types/api";
import { nodeToolbarPropsType } from "../../../../types/components";
import { FlowType } from "../../../../types/flow";
import {
  createFlowComponent,
  downloadNode,
  expandGroupNode,
  updateFlowPosition,
} from "../../../../utils/reactflowUtils";
import { classNames, cn, isThereModal } from "../../../../utils/utils";
import isWrappedWithClass from "../PageComponent/utils/is-wrapped-with-class";
import ToolbarSelectItem from "./toolbarSelectItem";

export default function NodeToolbarComponent({
  data,
  deleteNode,
  setShowNode,
  numberOfHandles,
  numberOfOutputHandles,
  showNode,
  name = "code",
  setShowState,
  onCloseAdvancedModal,
  updateNode,
  isOutdated,
}: nodeToolbarPropsType): JSX.Element {
  const version = useDarkStore((state) => state.version);
  const [showModalAdvanced, setShowModalAdvanced] = useState(false);
  const [showconfirmShare, setShowconfirmShare] = useState(false);
  const [showOverrideModal, setShowOverrideModal] = useState(false);
  const [flowComponent, setFlowComponent] = useState<FlowType>(
    createFlowComponent(cloneDeep(data), version),
  );
  const preventDefault = true;
  const isMac = navigator.platform.toUpperCase().includes("MAC");
  const nodeLength = Object.keys(data.node!.template).filter(
    (templateField) =>
      templateField.charAt(0) !== "_" &&
      data.node?.template[templateField]?.show &&
      (data.node.template[templateField]?.type === "str" ||
        data.node.template[templateField]?.type === "bool" ||
        data.node.template[templateField]?.type === "float" ||
        data.node.template[templateField]?.type === "code" ||
        data.node.template[templateField]?.type === "prompt" ||
        data.node.template[templateField]?.type === "file" ||
        data.node.template[templateField]?.type === "Any" ||
        data.node.template[templateField]?.type === "int" ||
        data.node.template[templateField]?.type === "dict" ||
        data.node.template[templateField]?.type === "NestedDict"),
  ).length;

  const hasStore = useStoreStore((state) => state.hasStore);
  const hasApiKey = useStoreStore((state) => state.hasApiKey);
  const validApiKey = useStoreStore((state) => state.validApiKey);
  const shortcuts = useShortcutsStore((state) => state.shortcuts);
  const unselectAll = useFlowStore((state) => state.unselectAll);
  function handleMinimizeWShortcut(e: KeyboardEvent) {
    if (isWrappedWithClass(e, "noflow")) return;
    e.preventDefault();
    if (isMinimal) {
      setShowState((show) => !show);
      setShowNode(data.showNode ?? true ? false : true);
      return;
    }
    setNoticeData({
      title:
        "Minimization are only available for components with one handle or fewer.",
    });
    return;
  }

  function handleGroupWShortcut(e: KeyboardEvent) {
    if (isWrappedWithClass(e, "noflow")) return;
    e.preventDefault();
    if (isGroup) {
      handleSelectChange("ungroup");
    }
  }

  function handleShareWShortcut(e: KeyboardEvent) {
    if (isWrappedWithClass(e, "noflow") && !showconfirmShare) return;
    e.preventDefault();
    if (hasApiKey || hasStore) {
      setShowconfirmShare((state) => !state);
    }
  }

  function handleCodeWShortcut(e: KeyboardEvent) {
    if (isWrappedWithClass(e, "noflow") && !openModal) return;
    e.preventDefault();
    if (hasCode) return setOpenModal((state) => !state);
    setNoticeData({ title: `You can not access ${data.id} code` });
  }

  function handleAdvancedWShortcut(e: KeyboardEvent) {
    if (isWrappedWithClass(e, "noflow") && !showModalAdvanced) return;
    e.preventDefault();
    setShowModalAdvanced((state) => !state);
  }

  function handleSaveWShortcut(e: KeyboardEvent) {
    if (isWrappedWithClass(e, "noflow") && !showOverrideModal) return;
    e.preventDefault();
    if (isSaved) {
      setShowOverrideModal((state) => !state);
      return;
    }
    if (hasCode && !isSaved) {
      saveComponent(cloneDeep(data), false);
      setSuccessData({ title: `${data.id} saved successfully` });
      return;
    }
  }

  function handleDocsWShortcut(e: KeyboardEvent) {
    e.preventDefault();
    if (data.node?.documentation) {
      return openInNewTab(data.node?.documentation);
    }
    setNoticeData({
      title: `${data.id} docs is not available at the moment.`,
    });
  }

  function handleDownloadWShortcut(e: KeyboardEvent) {
    e.preventDefault();
    downloadNode(flowComponent!);
  }

  function handleFreeze(e: KeyboardEvent) {
    if (isWrappedWithClass(e, "noflow")) return;
    e.preventDefault();
    if (data.node?.flow) return;
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
  }

  const advanced = useShortcutsStore((state) => state.advanced);
  const minimize = useShortcutsStore((state) => state.minimize);
  const component = useShortcutsStore((state) => state.component);
  const save = useShortcutsStore((state) => state.save);
  const docs = useShortcutsStore((state) => state.docs);
  const code = useShortcutsStore((state) => state.code);
  const group = useShortcutsStore((state) => state.group);
  const download = useShortcutsStore((state) => state.download);
  const freeze = useShortcutsStore((state) => state.freeze);

  useHotkeys(minimize, handleMinimizeWShortcut, { preventDefault });
  useHotkeys(group, handleGroupWShortcut, { preventDefault });
  useHotkeys(component, handleShareWShortcut, { preventDefault });
  useHotkeys(code, handleCodeWShortcut, { preventDefault });
  useHotkeys(advanced, handleAdvancedWShortcut, { preventDefault });
  useHotkeys(save, handleSaveWShortcut, { preventDefault });
  useHotkeys(docs, handleDocsWShortcut, { preventDefault });
  useHotkeys(download, handleDownloadWShortcut, { preventDefault });
  useHotkeys(freeze, handleFreeze);

  const isMinimal = numberOfHandles <= 1 && numberOfOutputHandles <= 1;
  const isGroup = data.node?.flow ? true : false;

  const frozen = data.node?.frozen ?? false;
  const paste = useFlowStore((state) => state.paste);
  const nodes = useFlowStore((state) => state.nodes);
  const edges = useFlowStore((state) => state.edges);
  const setNodes = useFlowStore((state) => state.setNodes);

  const setEdges = useFlowStore((state) => state.setEdges);
  const saveComponent = useFlowsManagerStore((state) => state.saveComponent);
  const getNodePosition = useFlowStore((state) => state.getNodePosition);
  const flows = useFlowsManagerStore((state) => state.flows);
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);

  //  useEffect(() => {
  //    if (openWDoubleClick) setShowModalAdvanced(true);
  //  }, [openWDoubleClick, setOpenWDoubleClick]);

  const openInNewTab = (url) => {
    window.open(url, "_blank", "noreferrer");
  };

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

  const handleSelectChange = (event) => {
    switch (event) {
      case "save":
        if (isSaved) {
          return setShowOverrideModal(true);
        }
        saveComponent(cloneDeep(data), false);
        break;
      case "freeze":
        if (data.node?.flow) return;
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
        break;
      case "code":
        setOpenModal(!openModal);
        break;
      case "advanced":
        setShowModalAdvanced(true);
        break;
      case "show":
        takeSnapshot();
        setShowNode(data.showNode ?? true ? false : true);
        break;
      case "Share":
        if (hasApiKey || hasStore) setShowconfirmShare(true);
        break;
      case "Download":
        downloadNode(flowComponent!);
        break;
      case "SaveAll":
        saveComponent(cloneDeep(data), false);
        break;
      case "documentation":
        if (data.node?.documentation) openInNewTab(data.node?.documentation);
        break;
      case "disabled":
        break;
      case "unselect":
        unselectAll();
        break;
      case "ungroup":
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
    }
  };

  const isSaved = flows.some((flow) =>
    Object.values(flow).includes(data.node?.display_name!),
  );

  function displayShortcut({
    name,
    shortcut,
  }: {
    name: string;
    shortcut: string;
  }): JSX.Element {
    let hasShift: boolean = false;
    const fixedShortcut = shortcut?.split("+");
    fixedShortcut.forEach((key) => {
      if (key.toLowerCase().includes("shift")) {
        hasShift = true;
      }
    });
    const filteredShortcut = fixedShortcut.filter(
      (key) => !key.toLowerCase().includes("shift"),
    );
    let shortcutWPlus: string[] = [];
    if (!hasShift) shortcutWPlus = filteredShortcut.join("+").split(" ");
    return (
      <div className="flex justify-center">
        <span> {name} </span>
        <span
          className={`ml-3 flex items-center rounded-sm bg-muted px-1.5 py-[0.1em] text-lg text-muted-foreground`}
        >
          <RenderIcons
            isMac={isMac}
            hasShift={hasShift}
            filteredShortcut={filteredShortcut}
            shortcutWPlus={shortcutWPlus}
          />
        </span>
      </div>
    );
  }

  const setNode = useFlowStore((state) => state.setNode);

  const handleOnNewValue = (
    newValue: string | string[] | boolean | Object[],
  ): void => {
    if (data.node!.template[name].value !== newValue) {
      takeSnapshot();
    }

    data.node!.template[name].value = newValue; // necessary to enable ctrl+z inside the input

    setNode(data.id, (oldNode) => {
      let newNode = cloneDeep(oldNode);

      newNode.data = {
        ...newNode.data,
      };

      newNode.data.node.template[name].value = newValue;

      return newNode;
    });
  };

  const handleNodeClass = (
    newNodeClass: APIClassType,
    code?: string,
    type?: string,
  ): void => {
    if (!data.node) return;
    if (data.node!.template[name].value !== code) {
      takeSnapshot();
    }

    setNode(data.id, (oldNode) => {
      let newNode = cloneDeep(oldNode);

      newNode.data = {
        ...newNode.data,
        node: newNodeClass,
        description: newNodeClass.description ?? data.node!.description,
        display_name: newNodeClass.display_name ?? data.node!.display_name,
      };

      if (type) {
        newNode.data.type = type;
      }

      newNode.data.node.template[name].value = code;

      return newNode;
    });
    updateNodeInternals(data.id);
  };

  const [openModal, setOpenModal] = useState(false);
  const hasCode = Object.keys(data.node!.template).includes("code");
  const [deleteIsFocus, setDeleteIsFocus] = useState(false);

  return (
    <>
      <div className="w-26 noflow nowheel nopan nodelete nodrag h-10">
        <span className="isolate inline-flex rounded-md shadow-sm">
          {hasCode && (
            <ShadTooltip
              content={displayShortcut(
                shortcuts.find(
                  ({ name }) => name.split(" ")[0].toLowerCase() === "code",
                )!,
              )}
              side="top"
            >
              <button
                className="relative inline-flex items-center rounded-l-md bg-background px-2 py-2 text-foreground shadow-md ring-1 ring-inset ring-ring transition-all duration-500 ease-in-out hover:bg-muted focus:z-10"
                onClick={() => {
                  setOpenModal(!openModal);
                }}
                data-testid="code-button-modal"
              >
                <IconComponent name="Code" className="h-4 w-4" />
              </button>
            </ShadTooltip>
          )}
          {nodeLength > 0 && (
            <ShadTooltip
              content={displayShortcut(
                shortcuts.find(
                  ({ name }) => name.split(" ")[0].toLowerCase() === "advanced",
                )!,
              )}
              side="top"
            >
              <button
                className={`${
                  isGroup ? "rounded-l-md" : ""
                } relative -ml-px inline-flex items-center bg-background px-2 py-2 text-foreground shadow-md ring-1 ring-inset ring-ring transition-all duration-500 ease-in-out hover:bg-muted focus:z-10`}
                onClick={() => {
                  setShowModalAdvanced(true);
                }}
                data-testid="advanced-button-modal"
              >
                <IconComponent name="Settings2" className="h-4 w-4" />
              </button>
            </ShadTooltip>
          )}

          {/*<ShadTooltip content={"Save"} side="top">
            <button
              data-testid="save-button-modal"
              className={classNames(
                "relative -ml-px inline-flex items-center bg-background px-2 py-2 text-foreground shadow-md ring-1 ring-inset ring-ring  transition-all duration-500 ease-in-out hover:bg-muted focus:z-10",
                hasCode ? " " : " rounded-l-md ",
              )}
              onClick={(event) => {
                event.preventDefault();
                if (isSaved) {
                  return setShowOverrideModal(true);
                }
                saveComponent(cloneDeep(data), false);
              }}
            >
              <IconComponent name="SaveAll" className="h-4 w-4" />
            </button>
          </ShadTooltip>*/}
          {!data.node?.flow && (
            <ShadTooltip
              content={displayShortcut(
                shortcuts.find(
                  ({ name }) => name.split(" ")[0].toLowerCase() === "freeze",
                )!,
              )}
              side="top"
            >
              <button
                className={classNames(
                  "relative -ml-px inline-flex items-center bg-background px-2 py-2 text-foreground shadow-md ring-1 ring-inset ring-ring transition-all duration-500 ease-in-out hover:bg-muted focus:z-10",
                )}
                onClick={(event) => {
                  event.preventDefault();
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
                }}
              >
                <IconComponent
                  name="Snowflake"
                  className={cn(
                    "h-4 w-4 transition-all",
                    // TODO UPDATE THIS COLOR TO BE A VARIABLE
                    frozen ? "animate-wiggle text-ice" : "",
                  )}
                />
              </button>
            </ShadTooltip>
          )}

          {/*<ShadTooltip content={"Duplicate"} side="top">
            <button
              data-testid="duplicate-button-modal"
              className={classNames(
                "relative -ml-px inline-flex items-center bg-background px-2 py-2 text-foreground shadow-md ring-1 ring-inset ring-ring  transition-all duration-500 ease-in-out hover:bg-muted focus:z-10",
              )}
              onClick={(event) => {
                event.preventDefault();
                handleSelectChange("duplicate");
              }}
            >
              <IconComponent name="Copy" className="h-4 w-4" />
            </button>
          </ShadTooltip>*/}

          <Select onValueChange={handleSelectChange} value="">
            <ShadTooltip content="All" side="top">
              <SelectTrigger>
                <div>
                  <div
                    data-testid="more-options-modal"
                    className={classNames(
                      "relative -ml-px inline-flex h-8 w-[31px] items-center rounded-r-md bg-background text-foreground shadow-md ring-1 ring-inset ring-ring transition-all duration-500 ease-in-out hover:bg-muted focus:z-10",
                    )}
                  >
                    <IconComponent
                      name="MoreHorizontal"
                      className="relative left-2 h-4 w-4"
                    />
                  </div>
                </div>
              </SelectTrigger>
            </ShadTooltip>
            <SelectContent>
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
                    value={"Advanced"}
                    icon={"Settings2"}
                    dataTestId="edit-button-modal"
                  />
                </SelectItem>
              )}
              <SelectItem value={"save"}>
                <ToolbarSelectItem
                  shortcut={
                    shortcuts.find((obj) => obj.name === "Save")?.shortcut!
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
              {/* {(!hasStore || !hasApiKey || !validApiKey) && (
                <SelectItem value={"Download"}>
                  <ToolbarSelectItem
                    shortcut={
                      shortcuts.find((obj) => obj.name === "Download")
                        ?.shortcut!
                    }
                    value={"Download"}
                    icon={"Download"}
                    dataTestId="Download-button-modal"
                  />
                </SelectItem>
              )} */}
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
              {isMinimal && (
                <SelectItem value={"show"}>
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
              {!data.node?.flow && (
                <SelectItem value="freeze">
                  <ToolbarSelectItem
                    shortcut={
                      shortcuts.find((obj) => obj.name === "Freeze")?.shortcut!
                    }
                    value={"Freeze"}
                    icon={"Snowflake"}
                    dataTestId="group-button-modal"
                    style={`${frozen ? " text-ice" : ""} transition-all`}
                  />
                </SelectItem>
              )}
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
              <SelectItem
                value={"delete"}
                className="focus:bg-red-400/[.20]"
                onFocus={() => setDeleteIsFocus(true)}
                onBlur={() => setDeleteIsFocus(false)}
              >
                <div className="font-red flex text-status-red">
                  <IconComponent
                    name="Trash2"
                    className="relative top-0.5 mr-2 h-4 w-4"
                  />{" "}
                  <span className="">Delete</span>{" "}
                  <span
                    className={`absolute right-2 top-2 flex items-center justify-center rounded-sm px-1 py-[0.2] ${
                      deleteIsFocus ? " " : "bg-muted"
                    }`}
                  >
                    <IconComponent
                      name="Delete"
                      className="h-4 w-4 stroke-2 text-red-400"
                    ></IconComponent>
                  </span>
                </div>
              </SelectItem>
            </SelectContent>
          </Select>

          <ConfirmationModal
            open={showOverrideModal}
            title={`Replace`}
            cancelText="Create New"
            confirmationText="Replace"
            size={"x-small"}
            icon={"SaveAll"}
            index={6}
            onConfirm={(index, user) => {
              saveComponent(cloneDeep(data), true);
              setSuccessData({ title: `${data.id} successfully overridden!` });
            }}
            onClose={setShowOverrideModal}
            onCancel={() => {
              saveComponent(cloneDeep(data), false);
              setSuccessData({ title: "New component successfully saved!" });
            }}
          >
            <ConfirmationModal.Content>
              <span>
                It seems {data.node?.display_name} already exists. Do you want
                to replace it with the current or create a new one?
              </span>
            </ConfirmationModal.Content>
          </ConfirmationModal>
          {showModalAdvanced && (
            <EditNodeModal
              //              setOpenWDoubleClick={setOpenWDoubleClick}
              data={data}
              nodeLength={nodeLength}
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
                <CodeAreaComponent
                  open={openModal}
                  setOpen={setOpenModal}
                  readonly={
                    data.node?.flow && data.node.template[name].dynamic
                      ? true
                      : false
                  }
                  dynamic={data.node?.template[name].dynamic ?? false}
                  setNodeClass={handleNodeClass}
                  nodeClass={data.node}
                  disabled={false}
                  value={data.node?.template[name].value ?? ""}
                  onChange={handleOnNewValue}
                  id={"code-input-node-toolbar-" + name}
                />
              )}
            </div>
          )}
        </span>
      </div>
    </>
  );
}
