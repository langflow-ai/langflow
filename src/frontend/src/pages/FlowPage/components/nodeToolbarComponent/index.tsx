import { useContext, useState } from "react";
import { useReactFlow, useUpdateNodeInternals } from "reactflow";
import ShadTooltip from "../../../../components/ShadTooltipComponent";
import IconComponent from "../../../../components/genericIconComponent";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "../../../../components/ui/select-custom";
import { FlowsContext } from "../../../../contexts/flowsContext";
import EditNodeModal from "../../../../modals/EditNodeModal";
import { nodeToolbarPropsType } from "../../../../types/components";
import {
  expandGroupNode,
  updateFlowPosition,
} from "../../../../utils/reactflowUtils";
import { classNames, getRandomKeyByssmm } from "../../../../utils/utils";

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

  const { paste } = useContext(FlowsContext);
  const reactFlowInstance = useReactFlow();
  const [showModalAdvanced, setShowModalAdvanced] = useState(false);
  const [selectedValue, setSelectedValue] = useState("");

  const handleSelectChange = (event) => {
    setSelectedValue(event);
    if (event.includes("advanced")) {
      return setShowModalAdvanced(true);
    }
    setShowModalAdvanced(false);
    if (event.includes("show")) {
      setShowNode((prev) => !prev);
      updateNodeInternals(data.id);
    }
    if (event.includes("disabled")) {
      return;
    }
    if (event.includes("ungroup")) {
      updateFlowPosition(position, data.node?.flow!);
      expandGroupNode(data, reactFlowInstance);
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

          {isMinimal || isGroup ? (
            <Select onValueChange={handleSelectChange} value={selectedValue}>
              <ShadTooltip content="More" side="top">
                <SelectTrigger>
                  <div id="advancedIcon">
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
                <SelectItem
                  value={
                    getRandomKeyByssmm() +
                    (nodeLength == 0 ? "disabled" : "advanced")
                  }
                >
                  <div
                    id="editAdvancedBtn"
                    className={
                      "flex " +
                      (nodeLength == 0
                        ? "text-muted-foreground"
                        : "text-primary")
                    }
                  >
                    <IconComponent
                      name="Settings2"
                      className="relative top-0.5 mr-2 h-4 w-4"
                    />{" "}
                    Edit{" "}
                  </div>{" "}
                </SelectItem>
                {isMinimal && (
                  <SelectItem value={getRandomKeyByssmm() + "show"}>
                    <div className="flex" id="editAdvanced">
                      <IconComponent
                        name={showNode ? "Minimize2" : "Maximize2"}
                        className="relative top-0.5 mr-2 h-4 w-4"
                      />
                      {showNode ? "Minimize" : "Expand"}
                    </div>
                  </SelectItem>
                )}
                {isGroup && (
                  <SelectItem value={getRandomKeyByssmm() + "ungroup"}>
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
          ) : (
            <ShadTooltip content="Edit" side="top">
              <div id="editAdvancedIcon">
                <button
                  disabled={nodeLength === 0}
                  onClick={() => setShowModalAdvanced(true)}
                  className={classNames(
                    "relative -ml-px inline-flex items-center rounded-r-md bg-background px-2 py-2 text-foreground shadow-md ring-1  ring-inset ring-ring transition-all duration-500 ease-in-out hover:bg-muted focus:z-10" +
                      (nodeLength == 0
                        ? " text-muted-foreground"
                        : " text-foreground")
                  )}
                >
                  <IconComponent name="Settings2" className="h-4 w-4 " />
                </button>
              </div>
            </ShadTooltip>
          )}

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
        </span>
      </div>
    </>
  );
}
