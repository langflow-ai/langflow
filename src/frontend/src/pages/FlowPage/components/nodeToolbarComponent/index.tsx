import _, { cloneDeep } from "lodash";
import { useEffect, useState } from "react";
import { useUpdateNodeInternals } from "reactflow";
import CodeAreaComponent from "../../../../components/codeAreaComponent";
import IconComponent from "../../../../components/genericIconComponent";
import ShadTooltip from "../../../../components/shadTooltipComponent";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "../../../../components/ui/select-custom";
import { postCustomComponent } from "../../../../controllers/API";
import ConfirmationModal from "../../../../modals/confirmationModal";
import EditNodeModal from "../../../../modals/editNodeModal";
import ShareModal from "../../../../modals/shareModal";
import useAlertStore from "../../../../stores/alertStore";
import { useDarkStore } from "../../../../stores/darkStore";
import useFlowStore from "../../../../stores/flowStore";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { useStoreStore } from "../../../../stores/storeStore";
import { useTypesStore } from "../../../../stores/typesStore";
import { APIClassType } from "../../../../types/api";
import { nodeToolbarPropsType } from "../../../../types/components";
import { FlowType } from "../../../../types/flow";
import {
  createFlowComponent,
  downloadNode,
  expandGroupNode,
  updateFlowPosition,
} from "../../../../utils/reactflowUtils";
import { classNames } from "../../../../utils/utils";
import ToolbarSelectItem from "./toolbarSelectItem";

export default function NodeToolbarComponent({
  data,
  deleteNode,
  setShowNode,
  numberOfHandles,
  showNode,
  name = "code",
  selected,
  updateNodeCode,
  setShowState,
  onCloseAdvancedModal,
  isOutdated,
}: nodeToolbarPropsType): JSX.Element {
  const nodeLength = Object.keys(data.node!.template).filter(
    (templateField) =>
      templateField.charAt(0) !== "_" &&
      data.node?.template[templateField].show &&
      (data.node.template[templateField].type === "str" ||
        data.node.template[templateField].type === "bool" ||
        data.node.template[templateField].type === "float" ||
        data.node.template[templateField].type === "code" ||
        data.node.template[templateField].type === "prompt" ||
        data.node.template[templateField].type === "file" ||
        data.node.template[templateField].type === "Any" ||
        data.node.template[templateField].type === "int" ||
        data.node.template[templateField].type === "dict" ||
        data.node.template[templateField].type === "NestedDict"),
  ).length;
  const templates = useTypesStore((state) => state.templates);
  const hasStore = useStoreStore((state) => state.hasStore);
  const hasApiKey = useStoreStore((state) => state.hasApiKey);
  const validApiKey = useStoreStore((state) => state.validApiKey);

  const isMinimal = numberOfHandles <= 1;
  const isGroup = data.node?.flow ? true : false;

  // const frozen = data.node?.frozen ?? false;
  const paste = useFlowStore((state) => state.paste);
  const nodes = useFlowStore((state) => state.nodes);
  const edges = useFlowStore((state) => state.edges);
  const setNodes = useFlowStore((state) => state.setNodes);

  const setEdges = useFlowStore((state) => state.setEdges);
  const unselectAll = useFlowStore((state) => state.unselectAll);
  const saveComponent = useFlowsManagerStore((state) => state.saveComponent);
  const getNodePosition = useFlowStore((state) => state.getNodePosition);
  const flows = useFlowsManagerStore((state) => state.flows);
  const version = useDarkStore((state) => state.version);
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
  const [showModalAdvanced, setShowModalAdvanced] = useState(false);
  const [showconfirmShare, setShowconfirmShare] = useState(false);
  const [showOverrideModal, setShowOverrideModal] = useState(false);
  const [flowComponent, setFlowComponent] = useState<FlowType>(
    createFlowComponent(cloneDeep(data), version),
  );

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
        );
        break;
      case "override":
        setShowOverrideModal(true);
        break;
      case "delete":
        deleteNode(data.id);
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
      case "update":
        takeSnapshot();
        // to update we must get the code from the templates in useTypesStore
        const thisNodeTemplate = templates[data.type].template;
        // if the template does not have a code key
        // return
        if (!thisNodeTemplate.code) return;

        const currentCode = thisNodeTemplate.code.value;
        if (data.node) {
          postCustomComponent(currentCode, data.node)
            .then((apiReturn) => {
              const { data } = apiReturn;
              if (data && updateNodeCode) {
                updateNodeCode(data, currentCode, "code");
              }
            })
            .catch((err) => {
              console.log(err);
            });
          setNode(data.id, (oldNode) => {
            let newNode = cloneDeep(oldNode);
            newNode.data = {
              ...data,
            };
            newNode.data.node.template.code.value = currentCode;
            return newNode;
          });
        }

        break;
    }
  };

  const isSaved = flows.some((flow) =>
    Object.values(flow).includes(data.node?.display_name!),
  );

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

  const handleNodeClass = (newNodeClass: APIClassType, code?: string): void => {
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

      newNode.data.node.template[name].value = code;

      return newNode;
    });
    updateNodeInternals(data.id);
  };

  const [openModal, setOpenModal] = useState(false);
  const hasCode = Object.keys(data.node!.template).includes("code");

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (
        selected &&
        (hasApiKey || hasStore) &&
        (event.ctrlKey || event.metaKey) &&
        event.key === "u"
      ) {
        event.preventDefault();
        handleSelectChange("update");
      }
      if (
        selected &&
        isGroup &&
        (event.ctrlKey || event.metaKey) &&
        event.key === "g"
      ) {
        event.preventDefault();
        handleSelectChange("ungroup");
      }
      if (
        selected &&
        (hasApiKey || hasStore) &&
        (event.ctrlKey || event.metaKey) &&
        event.shiftKey &&
        event.key === "S"
      ) {
        event.preventDefault();
        setShowconfirmShare((state) => !state);
      }

      if (
        selected &&
        (event.ctrlKey || event.metaKey) &&
        event.shiftKey &&
        event.key === "Q"
      ) {
        event.preventDefault();
        if (isMinimal) {
          setShowState((show) => !show);
          setShowNode(data.showNode ?? true ? false : true);
          return;
        }
        setNoticeData({
          title:
            "Minimization are only available for nodes with one handle or fewer.",
        });
      }
      if (
        selected &&
        (event.ctrlKey || event.metaKey) &&
        event.shiftKey &&
        event.key === "U"
      ) {
        event.preventDefault();
        if (hasCode) return setOpenModal((state) => !state);
        setNoticeData({ title: `You can not access ${data.id} code` });
      }
      if (
        selected &&
        (event.ctrlKey || event.metaKey) &&
        event.shiftKey &&
        event.key === "A"
      ) {
        event.preventDefault();
        setShowModalAdvanced((state) => !state);
      }
      if (selected && (event.ctrlKey || event.metaKey) && event.key === "s") {
        if (isSaved) {
          event.preventDefault();
          return setShowOverrideModal((state) => !state);
        }
        if (hasCode) {
          event.preventDefault();
          saveComponent(cloneDeep(data), false);
          setSuccessData({ title: `${data.id} saved successfully` });
        }
      }
      if (
        selected &&
        (event.ctrlKey || event.metaKey) &&
        event.shiftKey &&
        event.key === "D"
      ) {
        event.preventDefault();
        if (data.node?.documentation) {
          return openInNewTab(data.node?.documentation);
        }
        setNoticeData({
          title: `${data.id} docs is not available at the moment.`,
        });
      }
      if (selected && (event.ctrlKey || event.metaKey) && event.key === "j") {
        event.preventDefault();
        downloadNode(flowComponent!);
      }
    }

    document.addEventListener("keydown", onKeyDown);

    return () => {
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [isSaved, showNode, data.showNode, isMinimal]);

  return (
    <>
      <div className="w-26 h-10">
        <span className="isolate inline-flex rounded-md shadow-sm">
          {hasCode && (
            <ShadTooltip content="Code" side="top">
              <button
                className="relative inline-flex items-center rounded-l-md  bg-background px-2 py-2 text-foreground shadow-md ring-1 ring-inset ring-ring transition-all duration-500 ease-in-out hover:bg-muted focus:z-10"
                onClick={() => {
                  setOpenModal(!openModal);
                }}
                data-testid="code-button-modal"
              >
                <IconComponent name="Code" className="h-4 w-4" />
              </button>
            </ShadTooltip>
          )}

          <ShadTooltip content={"Save"} side="top">
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
          </ShadTooltip>

          <ShadTooltip content={"Duplicate"} side="top">
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
          </ShadTooltip>

          {/* <ShadTooltip content="Freeze" side="top">
            <button
              className={classNames(
                "relative -ml-px inline-flex items-center bg-background px-2 py-2 text-foreground shadow-md ring-1 ring-inset ring-ring  transition-all duration-500 ease-in-out hover:bg-muted focus:z-10"
              )}
              onClick={(event) => {
                event.preventDefault();
                setNode(data.id, (old) => ({
                  ...old,
                  data: {
                    ...old.data,
                    node: {
                      ...old.data.node,
                      // frozen: old.data?.node?.frozen ? false : true,
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
                  frozen ? "animate-wiggle text-ice" : ""
                )}
              />
            </button>
          </ShadTooltip> */}

          <Select onValueChange={handleSelectChange} value="">
            <ShadTooltip content="More" side="top">
              <SelectTrigger>
                <div>
                  <div
                    data-testid="more-options-modal"
                    className={classNames(
                      "relative -ml-px inline-flex h-8 w-[31px] items-center rounded-r-md bg-background text-foreground  shadow-md ring-1 ring-inset  ring-ring transition-all duration-500 ease-in-out hover:bg-muted focus:z-10",
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
              {nodeLength > 0 && (
                <SelectItem value={nodeLength === 0 ? "disabled" : "advanced"}>
                  <ToolbarSelectItem
                    keyboardKey="A"
                    isMac={navigator.userAgent.toUpperCase().includes("MAC")}
                    shift={true}
                    value={"Advanced"}
                    icon={"Settings2"}
                    dataTestId="edit-button-modal"
                  />
                </SelectItem>
              )}
              {/* <SelectItem value={"duplicate"}>
                <ToolbarSelectItem
                  keyboardKey="D"
                  isMac={navigator.userAgent.toUpperCase().includes("MAC")}
                  shift={false}
                  value={"Duplicate"}
                  icon={"Copy"}
                  dataTestId="duplicate-button-modal"
                />
              </SelectItem> */}
              <SelectItem value={"copy"}>
                <ToolbarSelectItem
                  keyboardKey="C"
                  isMac={navigator.userAgent.toUpperCase().includes("MAC")}
                  shift={false}
                  value={"Copy"}
                  icon={"Clipboard"}
                  dataTestId="copy-button-modal"
                />
              </SelectItem>
              {isOutdated && (
                <SelectItem value={"update"}>
                  <ToolbarSelectItem
                    keyboardKey="U"
                    isMac={navigator.userAgent.toUpperCase().includes("MAC")}
                    shift={false}
                    value={"Update"}
                    icon={"Code"}
                    dataTestId="update-button-modal"
                    ping={isOutdated}
                  />
                </SelectItem>
              )}
              {hasStore && (
                <SelectItem
                  value={"Share"}
                  disabled={!hasApiKey || !validApiKey}
                >
                  <ToolbarSelectItem
                    keyboardKey="S"
                    isMac={navigator.userAgent.toUpperCase().includes("MAC")}
                    shift={true}
                    value={"Share"}
                    icon={"Share3"}
                    styleObj={{
                      iconClasses: "relative top-0.5 -m-1 mr-[0.25rem] h-6 w-6",
                    }}
                    dataTestId="share-button-modal"
                  />
                </SelectItem>
              )}
              {(!hasStore || !hasApiKey || !validApiKey) && (
                <SelectItem value={"Download"}>
                  <ToolbarSelectItem
                    value="Download"
                    shift={false}
                    isMac={navigator.userAgent.toUpperCase().includes("MAC")}
                    icon="Download"
                    styleObj={{ iconClasses: "relative top-0.5 mr-2 h-4 w-4" }}
                    keyboardKey={"J"}
                    dataTestId={"Dowload-button-nodeToolbar"}
                  />
                </SelectItem>
              )}
              <SelectItem
                value={"documentation"}
                disabled={data.node?.documentation === ""}
              >
                <ToolbarSelectItem
                  keyboardKey="D"
                  isMac={navigator.userAgent.toUpperCase().includes("MAC")}
                  shift={true}
                  value={"Docs"}
                  icon={"FileText"}
                  dataTestId="docs-button-modal"
                />
              </SelectItem>
              {isMinimal && (
                <SelectItem value={"show"}>
                  <ToolbarSelectItem
                    icon={showNode ? "Minimize2" : "Maximize2"}
                    value={showNode ? "Minimize" : "Expand"}
                    isMac={navigator.userAgent.toUpperCase().includes("MAC")}
                    shift={true}
                    keyboardKey={"Q"}
                    dataTestId={"minimize-button-nodeToolbar"}
                  />
                </SelectItem>
              )}
              {isGroup && (
                <SelectItem value="ungroup">
                  <div className="flex">
                    <IconComponent
                      name="Ungroup"
                      className="relative top-0.5 mr-2 h-4 w-4 "
                    />{" "}
                    <span className="">Ungroup</span>{" "}
                    {navigator.userAgent.toUpperCase().includes("MAC") ? (
                      <IconComponent
                        name="Command"
                        className="absolute right-[1.15rem] top-[0.65em] h-3.5 w-3.5 stroke-2"
                      ></IconComponent>
                    ) : (
                      <span className="absolute right-[1.30rem] top-[0.40em] stroke-2">
                        Ctrl +{" "}
                      </span>
                    )}
                    <span className="absolute right-2 top-[0.43em]">G</span>
                  </div>
                </SelectItem>
              )}

              <SelectItem value={"delete"} className="focus:bg-red-400/[.20]">
                <div className="font-red flex text-status-red">
                  <IconComponent
                    name="Trash2"
                    className="relative top-0.5 mr-2 h-4 w-4 "
                  />{" "}
                  <span className="">Delete</span>{" "}
                  <span>
                    <IconComponent
                      name="Delete"
                      className="absolute right-2 top-2 h-4 w-4 stroke-2 text-red-400"
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
              setSuccessData({ title: "New node successfully saved!" });
            }}
          >
            <ConfirmationModal.Content>
              <span>
                It seems {data.node?.display_name} already exists. Do you want
                to replace it with the current or create a new one?
              </span>
            </ConfirmationModal.Content>
          </ConfirmationModal>
          <EditNodeModal
            data={data}
            nodeLength={nodeLength}
            open={showModalAdvanced}
            setOpen={setShowModalAdvanced}
          />
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
