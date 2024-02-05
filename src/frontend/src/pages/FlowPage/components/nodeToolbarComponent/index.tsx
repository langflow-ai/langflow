import { cloneDeep } from "lodash";
import { useEffect, useState } from "react";
import ShadTooltip from "../../../../components/ShadTooltipComponent";
import IconComponent from "../../../../components/genericIconComponent";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "../../../../components/ui/select-custom";
import ConfirmationModal from "../../../../modals/ConfirmationModal";
import EditNodeModal from "../../../../modals/EditNodeModal";
import ShareModal from "../../../../modals/shareModal";
import { useDarkStore } from "../../../../stores/darkStore";
import useFlowStore from "../../../../stores/flowStore";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { useStoreStore } from "../../../../stores/storeStore";
import { nodeToolbarPropsType } from "../../../../types/components";
import { FlowType } from "../../../../types/flow";
import {
  createFlowComponent,
  downloadNode,
  expandGroupNode,
  updateFlowPosition,
} from "../../../../utils/reactflowUtils";
import { classNames } from "../../../../utils/utils";

export default function NodeToolbarComponent({
  data,
  deleteNode,
  position,
  setShowNode,
  numberOfHandles,
  showNode,
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
        data.node.template[templateField].type === "NestedDict")
  ).length;

  const hasStore = useStoreStore((state) => state.hasStore);
  const hasApiKey = useStoreStore((state) => state.hasApiKey);
  const validApiKey = useStoreStore((state) => state.validApiKey);

  const isMinimal = numberOfHandles <= 1;
  const isGroup = data.node?.flow ? true : false;

  const paste = useFlowStore((state) => state.paste);
  const nodes = useFlowStore((state) => state.nodes);
  const edges = useFlowStore((state) => state.edges);
  const setNodes = useFlowStore((state) => state.setNodes);
  const setEdges = useFlowStore((state) => state.setEdges);

  const saveComponent = useFlowsManagerStore((state) => state.saveComponent);
  const flows = useFlowsManagerStore((state) => state.flows);
  const version = useDarkStore((state) => state.version);
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
  const [showModalAdvanced, setShowModalAdvanced] = useState(false);
  const [showconfirmShare, setShowconfirmShare] = useState(false);
  const [showOverrideModal, setShowOverrideModal] = useState(false);

  const [flowComponent, setFlowComponent] = useState<FlowType>();

  const openInNewTab = (url) => {
    window.open(url, "_blank", "noreferrer");
  };

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
          updateFlowPosition(position, data.node?.flow!),
          data.node!.template,
          nodes,
          edges,
          setNodes,
          setEdges
        );
        break;
      case "override":
        setShowOverrideModal(true);
        break;
    }
  };

  const isSaved = flows.some((flow) =>
    Object.values(flow).includes(data.node?.display_name!)
  );

  return (
    <>
      <div className="w-26 h-10">
        <span className="isolate inline-flex rounded-md shadow-sm">
          <ShadTooltip content="Delete" side="top">
            <button
              className="relative inline-flex items-center rounded-l-md  bg-background px-2 py-2 text-foreground shadow-md ring-1 ring-inset ring-ring transition-all duration-500 ease-in-out hover:bg-muted focus:z-10"
              onClick={() => {
                deleteNode(data.id);
              }}
              data-testid="delete-button-modal"
            >
              <IconComponent name="Trash2" className="h-4 w-4" />
            </button>
          </ShadTooltip>

          <ShadTooltip content="Duplicate" side="top">
            <button
              className={classNames(
                "relative -ml-px inline-flex items-center bg-background px-2 py-2 text-foreground shadow-md ring-1 ring-inset ring-ring  transition-all duration-500 ease-in-out hover:bg-muted focus:z-10"
              )}
              onClick={(event) => {
                event.preventDefault();
                paste(
                  {
                    nodes: [nodes.find((node) => node.id === data.id)!],
                    edges: [],
                  },
                  {
                    x: 50,
                    y: 10,
                    paneX: nodes.find((node) => node.id === data.id)?.position
                      .x,
                    paneY: nodes.find((node) => node.id === data.id)?.position
                      .y,
                  }
                );
              }}
            >
              <IconComponent name="Copy" className="h-4 w-4" />
            </button>
          </ShadTooltip>
          {hasStore && (
            <ShadTooltip content="Share" side="top">
              <button
                className={classNames(
                  "relative -ml-px inline-flex items-center bg-background px-2 py-2 text-foreground shadow-md ring-1 ring-inset ring-ring  transition-all duration-500 ease-in-out hover:bg-muted focus:z-10",
                  !hasApiKey || !validApiKey ? " text-muted-foreground" : ""
                )}
                onClick={(event) => {
                  event.preventDefault();
                  if (hasApiKey || hasStore) setShowconfirmShare(true);
                }}
              >
                <IconComponent name="Share3" className="-m-1 h-6 w-6" />
              </button>
            </ShadTooltip>
          )}

          <Select onValueChange={handleSelectChange} value="">
            <ShadTooltip content="More" side="top">
              <SelectTrigger>
                <div>
                  <div
                    data-testid="more-options-modal"
                    className={classNames(
                      "relative -ml-px inline-flex h-8 w-[31px] items-center rounded-r-md bg-background text-foreground  shadow-md ring-1 ring-inset  ring-ring transition-all duration-500 ease-in-out hover:bg-muted focus:z-10"
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
                  <div className="flex" data-testid="edit-button-modal">
                    <IconComponent
                      name="Settings2"
                      className="relative top-0.5 mr-2 h-4 w-4"
                    />{" "}
                    Edit{" "}
                  </div>{" "}
                </SelectItem>
              )}

              {isSaved ? (
                <SelectItem value={"override"}>
                  <div className="flex" data-testid="save-button-modal">
                    <IconComponent
                      name="SaveAll"
                      className="relative top-0.5 mr-2 h-4 w-4"
                    />{" "}
                    Save{" "}
                  </div>{" "}
                </SelectItem>
              ) : (
                <SelectItem value={"SaveAll"}>
                  <div className="flex" data-testid="save-button-modal">
                    <IconComponent
                      name="SaveAll"
                      className="relative top-0.5 mr-2 h-4 w-4"
                    />{" "}
                    Save{" "}
                  </div>{" "}
                </SelectItem>
              )}
              {!hasStore && (
                <SelectItem value={"Download"}>
                  <div className="flex">
                    <IconComponent
                      name="Download"
                      className="relative top-0.5 mr-2 h-4 w-4"
                    />{" "}
                    Download{" "}
                  </div>{" "}
                </SelectItem>
              )}
              <SelectItem
                value={"documentation"}
                disabled={data.node?.documentation === ""}
              >
                <div className="flex">
                  <IconComponent
                    name="FileText"
                    className="relative top-0.5 mr-2 h-4 w-4"
                  />{" "}
                  {data.node?.documentation === ""
                    ? "Coming Soon"
                    : "Documentation"}
                </div>{" "}
              </SelectItem>
              {isMinimal && (
                <SelectItem value={"show"}>
                  <div className="flex">
                    <IconComponent
                      name={showNode ? "Minimize2" : "Maximize2"}
                      className="relative top-0.5 mr-2 h-4 w-4"
                    />
                    {showNode ? "Minimize" : "Expand"}
                  </div>
                </SelectItem>
              )}
              {isGroup && (
                <SelectItem value="ungroup">
                  <div className="flex">
                    <IconComponent
                      name="Combine"
                      className="relative top-0.5 mr-2 h-4 w-4"
                    />{" "}
                    Ungroup{" "}
                  </div>
                </SelectItem>
              )}
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
            }}
            onClose={setShowOverrideModal}
            onCancel={() => saveComponent(cloneDeep(data), false)}
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
          <ShareModal
            open={showconfirmShare}
            setOpen={setShowconfirmShare}
            is_component={true}
            component={flowComponent!}
          />
        </span>
      </div>
    </>
  );
}
