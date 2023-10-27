import { cloneDeep } from "lodash";
import { useContext, useEffect, useState } from "react";
import { useReactFlow, useUpdateNodeInternals } from "reactflow";
import ShadTooltip from "../../../../components/ShadTooltipComponent";
import IconComponent from "../../../../components/genericIconComponent";
import { TagsSelector } from "../../../../components/tagsSelectorComponent";
import ToggleShadComponent from "../../../../components/toggleShadComponent";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "../../../../components/ui/select-custom";
import { alertContext } from "../../../../contexts/alertContext";
import { TabsContext } from "../../../../contexts/tabsContext";
import { saveFlowStore } from "../../../../controllers/API";
import ConfirmationModal from "../../../../modals/ConfirmationModal";
import EditNodeModal from "../../../../modals/EditNodeModal";
import { nodeToolbarPropsType } from "../../../../types/components";
import {
  createFlowComponent,
  downloadNode,
  expandGroupNode,
  updateFlowPosition,
} from "../../../../utils/reactflowUtils";
import { classNames } from "../../../../utils/utils";

export default function NodeToolbarComponent({
  data,
  setData,
  deleteNode,
  position,
  setShowNode,
  numberOfHandles,
  showNode,
}: nodeToolbarPropsType): JSX.Element {
  const [nodeLength, setNodeLength] = useState(
    Object.keys(data.node!.template).filter(
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
          data.node.template[templateField].type === "int")
    ).length
  );
  const updateNodeInternals = useUpdateNodeInternals();
  const { getNodeId } = useContext(TabsContext);
  const { setErrorData, setSuccessData } = useContext(alertContext);

  function canMinimize() {
    let countHandles: number = 0;
    numberOfHandles.forEach((bool) => {
      if (bool) countHandles += 1;
    });
    if (countHandles > 1) return false;
    return true;
  }
  const isMinimal = canMinimize();
  const isGroup = data.node?.flow ? true : false;

  const { paste, saveComponent } = useContext(TabsContext);
  const reactFlowInstance = useReactFlow();
  const [showModalAdvanced, setShowModalAdvanced] = useState(false);
  const [showconfirmShare, setShowconfirmShare] = useState(false);
  const [selectedValue, setSelectedValue] = useState("");
  const [sharePublic, setSharePublic] = useState(true);
  const [tags, setTags] = useState<string[]>([]);
  const [selectedTags, setSelectedTags] = useState<Set<string>>(new Set());

  useEffect(() => {
    //TODO: get tags from api
    setTags(["teste1", "teste2"]);
  }, []);

  function handleTagSelection(tag: string) {
    setSelectedTags((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(tag)) {
        newSet.delete(tag);
      } else {
        newSet.add(tag);
      }
      return newSet;
    });
  }

  function handleShareComponent() {
    const componentFlow = cloneDeep(data);
    saveComponent(componentFlow).then(() => {
      saveFlowStore(
        createFlowComponent(componentFlow),
        Array.from(selectedTags),
        sharePublic
      ).then(
        (_) => {
          setSuccessData({
            title: "Component shared successfully",
          });
        },
        (err) => {
          setErrorData({
            title: "Error sharing component",
            list: [err["response"]["data"]["detail"]],
          });
        }
      );
    });
  }
  const handleSelectChange = (event) => {
    switch (event) {
      case "advanced":
        setShowModalAdvanced(true);
        break;
      case "show":
        setShowNode((prev) => !prev);
        updateNodeInternals(data.id);
        break;
      case "Download":
        downloadNode(createFlowComponent(cloneDeep(data)));
        break;
      case "Share":
        setShowconfirmShare(true);
        break;
      case "SaveAll":
        saveComponent(cloneDeep(data));
        break;
      case "disabled":
        break;
      case "ungroup":
        updateFlowPosition(position, data.node?.flow!);
        expandGroupNode(data, reactFlowInstance, getNodeId);
        break;
    }
  };

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
                    nodes: [reactFlowInstance.getNode(data.id)],
                    edges: [],
                  },
                  {
                    x: 50,
                    y: 10,
                    paneX: reactFlowInstance.getNode(data.id)?.position.x,
                    paneY: reactFlowInstance.getNode(data.id)?.position.y,
                  }
                );
              }}
            >
              <IconComponent name="Copy" className="h-4 w-4" />
            </button>
          </ShadTooltip>

          <ShadTooltip
            content={
              data.node?.documentation === "" ? "Coming Soon" : "Documentation"
            }
            side="top"
          >
            <a
              className={classNames(
                "relative -ml-px inline-flex items-center bg-background px-2 py-2 text-foreground shadow-md ring-1 ring-inset ring-ring  transition-all duration-500 ease-in-out hover:bg-muted focus:z-10" +
                  (data.node?.documentation === ""
                    ? " text-muted-foreground"
                    : " text-foreground")
              )}
              target="_blank"
              rel="noopener noreferrer"
              href={data.node?.documentation}
              // deactivate link if no documentation is provided
              onClick={(event) => {
                if (data.node?.documentation === "") {
                  event.preventDefault();
                }
              }}
            >
              <IconComponent name="FileText" className="h-4 w-4 " />
            </a>
          </ShadTooltip>

          <Select onValueChange={handleSelectChange} value={selectedValue}>
            <ShadTooltip content="More" side="top">
              <SelectTrigger>
                <div>
                  <div
                    className={classNames(
                      "relative -ml-px inline-flex h-8 w-[31px] items-center rounded-r-md bg-background text-foreground shadow-md ring-1 ring-inset  ring-ring transition-all duration-500 ease-in-out hover:bg-muted focus:z-10" +
                        (nodeLength == 0
                          ? " text-muted-foreground"
                          : " text-foreground")
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
              <SelectItem value={nodeLength == 0 ? "disabled" : "advanced"}>
                <div className="flex">
                  <IconComponent
                    name="Settings2"
                    className="relative top-0.5 mr-2 h-4 w-4"
                  />{" "}
                  Edit{" "}
                </div>{" "}
              </SelectItem>
              <SelectItem value={"SaveAll"}>
                <div className="flex">
                  <IconComponent
                    name="SaveAll"
                    className="relative top-0.5 mr-2 h-4 w-4"
                  />{" "}
                  Save{" "}
                </div>{" "}
              </SelectItem>
              <SelectItem value={"Share"}>
                <div className="flex">
                  <IconComponent
                    name="Share2"
                    className="relative top-0.5 mr-2 h-4 w-4"
                  />{" "}
                  Share{" "}
                </div>{" "}
              </SelectItem>
              <SelectItem value={"Download"}>
                <div className="flex">
                  <IconComponent
                    name="Download"
                    className="relative top-0.5 mr-2 h-4 w-4"
                  />{" "}
                  Download{" "}
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
                      name="Ungroup"
                      className="relative top-0.5 mr-2 h-4 w-4"
                    />{" "}
                    Ungroup{" "}
                  </div>
                </SelectItem>
              )}
            </SelectContent>
          </Select>

          {showModalAdvanced && (
            <EditNodeModal
              data={data}
              setData={setData}
              nodeLength={nodeLength}
              open={showModalAdvanced}
              onClose={(modal) => {
                setShowModalAdvanced(modal);
              }}
            >
              <></>
            </EditNodeModal>
          )}
          {showconfirmShare && (
            <ConfirmationModal
              key={data.id}
              index={0}
              size="smaller"
              modalContentTitle="Are you sure you want to share this component?"
              title="Share Component"
              confirmationText="Share"
              icon="Share2"
              onConfirm={() => {
                handleShareComponent();
              }}
              titleHeader=""
              cancelText="Cancel"
              open={showconfirmShare}
              onClose={(modal) => {
                setShowconfirmShare(modal);
              }}
            >
              <ConfirmationModal.Content>
                <div className="flex h-full w-full flex-col gap-7">
                  <div className="flex justify-start align-middle">
                    <ToggleShadComponent
                      disabled={false}
                      size="medium"
                      setEnabled={setSharePublic}
                      enabled={sharePublic}
                    />
                    <div>
                      {sharePublic
                        ? "This component will be avaliable for everyone"
                        : "This component will be avaliable just for you"}
                    </div>
                  </div>
                  <div className="w-full pt-2">
                    <span className="text-sm">
                      Add some tags to your component
                    </span>
                    <TagsSelector
                      tags={tags}
                      selectedTags={selectedTags}
                      setSelectedTags={handleTagSelection}
                    />
                  </div>
                </div>{" "}
              </ConfirmationModal.Content>
              <ConfirmationModal.Trigger>
                <div></div>
              </ConfirmationModal.Trigger>
            </ConfirmationModal>
          )}
        </span>
      </div>
    </>
  );
}
