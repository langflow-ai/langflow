import { useContext, useEffect, useRef, useState } from "react";
import { FlowType, NodeDataType } from "../../types/flow";
import {
  classNames,
  concatFlows,
  expandGroupNode,
  isValidConnection,
  nodeColors,
  nodeIcons,
  toNormalCase,
  updateFlowPosition,
} from "../../utils";
import { typesContext } from "../../contexts/typesContext";
import { Handle, NodeToolbar, Position, useUpdateNodeInternals } from "reactflow";
import {
  ArrowsPointingOutIcon,
  Cog6ToothIcon,
  TrashIcon,
} from "@heroicons/react/24/outline";
import InputParameterComponent from "../GenericNode/components/inputParameterComponent";
import { TabsContext } from "../../contexts/tabsContext";
import InputComponent from "../../components/inputComponent";
import NodeModal from "../../modals/NodeModal";
import { PopUpContext } from "../../contexts/popUpContext";
import ParameterComponent from "../GenericNode/components/parameterComponent";
import NodeToolbarComponent from "../../pages/FlowPage/components/nodeToolbarComponent";

export default function GroupNode({
  data,
  selected,
  xPos,
  yPos,
}: {
  data: NodeDataType;
  selected: boolean;
  xPos: number;
  yPos: number;
}) {
  const [isValid, setIsValid] = useState(true);
  const { reactFlowInstance, deleteNode, types } = useContext(typesContext);
  const { setDisableCopyPaste } = useContext(TabsContext);
  const Icon = nodeIcons["custom"];
  const ref = useRef(null);
  const updateNodeInternals = useUpdateNodeInternals();
  const [flowHandlePosition, setFlowHandlePosition] = useState(0);
  const [inputName, setInputName] = useState(true);
  const [nodeName, setNodeName] = useState(data.node.flow.name);
  const [inputDescription, setInputDescription] = useState(false);
  const [nodeDescription, setNodeDescription] = useState(
    data.node.flow.description
  );
  const { openPopUp } = useContext(PopUpContext);

  useEffect(() => {
    if (ref.current && ref.current.offsetTop && ref.current.clientHeight) {
      setFlowHandlePosition(
        ref.current.offsetTop + ref.current.clientHeight / 2
      );
      updateNodeInternals(data.id);
    }
  }, [data.id, ref, updateNodeInternals, ref.current]);

  useEffect(() => {
    updateNodeInternals(data.id);
  }, [data.id, flowHandlePosition, updateNodeInternals]);
  // console.log(data)
  // console.log(Object.keys(data.node.template).length,data.node.template)
  return (
    <>
      <NodeToolbar>
        <NodeToolbarComponent
          data={data}
          openPopUp={openPopUp}
          deleteNode={deleteNode}
        ></NodeToolbarComponent>
      </NodeToolbar>
      <div
        className={classNames(
          isValid ? "animate-pulse-green" : "border-red-outline",
          selected ? "border border-blue-500" : "border dark:border-gray-700",
          "prompt-node relative flex w-96 flex-col justify-center rounded-lg bg-white dark:bg-gray-900"
        )}
      >
        <div className="flex w-full items-center justify-between gap-8 rounded-t-lg border-b bg-gray-50 p-4 dark:border-b-gray-700 dark:bg-gray-800 dark:text-white ">
          <div className="flex w-full items-center gap-2 truncate text-lg">
            <Icon
              className="h-10 w-10 rounded p-1"
              style={{
                color: nodeColors["custom"] ?? nodeColors.unknown,
              }}
            />
            {inputName ? (
              <InputComponent
                autoFocus
                onBlur={() => {
                  setInputName(false);
                  if (nodeName.trim() !== "") {
                    setNodeName(nodeName);
                    data.node.flow.name = nodeName;
                  } else {
                    setNodeName(data.node.flow.name);
                  }
                }}
                value={nodeName}
                onChange={setNodeName}
                password={false}
              />
            ) : (
              <div
                className="ml-2 truncate"
                onDoubleClick={() => {
                  setInputName(true);
                }}
              >
                {nodeName}
              </div>
            )}
            <div>
              {/* <div className="relative w-5 h-5">
                    <CheckCircleIcon
                      className={classNames(
                        validationStatus && validationStatus.valid ? "text-green-500 opacity-100" : "text-red-500 opacity-0",
                        "absolute w-5 hover:text-gray-500 hover:dark:text-gray-300 transition-all ease-in-out duration-300"
                      )}
                    />
                    <ExclamationCircleIcon
                      className={classNames(
                        validationStatus && !validationStatus.valid ? "text-red-500 opacity-100" : "text-red-500 opacity-0",
                        "w-5 absolute hover:text-gray-500 hover:dark:text-gray-600 transition-all ease-in-out duration-300"
                      )}
                    />
                    <EllipsisHorizontalCircleIcon
                      className={classNames(
                        !validationStatus ? "text-yellow-500 opacity-100" : "text-red-500 opacity-0",
                        "w-5 absolute hover:text-gray-500 hover:dark:text-gray-600 transition-all ease-in-out duration-300"
                      )}
                    />
                  </div> */}
            </div>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => {
                updateFlowPosition({ x: xPos, y: yPos }, data.node.flow);
                expandGroupNode(
                  data.node.flow,
                  reactFlowInstance,
                  data.node.template
                );
              }}
            >
              <ArrowsPointingOutIcon className="h-6 w-6 hover:text-blue-500 dark:text-gray-300 dark:hover:text-blue-500" />
            </button>
            <button
              className="relative"
              onClick={(event) => {
                event.preventDefault();
                openPopUp(<NodeModal data={data} />);
              }}
            >
              <div className=" absolute -right-1 -top-2 text-red-600">
                {Object.keys(data.node.template).some(
                  (t) =>
                    data.node.template[t].advanced &&
                    data.node.template[t].required
                )
                  ? " *"
                  : ""}
              </div>
            </button>
          </div>
        </div>
        <div className="h-full w-full py-5">
          <div className="w-full px-5 pb-3 text-sm text-gray-500 dark:text-gray-300">
            {inputDescription ? (
              <textarea
                onFocus={() => {
                  setDisableCopyPaste(true);
                }}
                autoFocus
                className="h-max w-full resize-none rounded-md bg-transparent outline-gray-300 hover:outline focus:border-none  focus:outline active:outline"
                onBlur={() => {
                  setInputDescription(false);
                  setDisableCopyPaste(false);
                  if (nodeDescription.trim() !== "") {
                    setNodeDescription(nodeDescription);
                    data.node.flow.description = nodeDescription;
                  } else {
                    setNodeDescription(data.node.flow.description);
                  }
                }}
                value={nodeDescription}
                onChange={(e) => {
                  setNodeDescription(e.target.value);
                }}
              />
            ) : (
              <div
                className="ml-2 truncate"
                onDoubleClick={() => {
                  setInputDescription(true);
                }}
              >
                {nodeDescription.trim().length > 0
                  ? nodeDescription
                  : "No description"}
              </div>
            )}
          </div>
          <>
            {Object.keys(data.node.template)
              .filter((field_name) => field_name.charAt(0) !== "_")
              .map((field_name: string, idx) => (
                <div key={idx}>
                  {data.node.template[field_name].show &&
                    !data.node.template[field_name].root &&
                    !data.node.template[field_name].advanced ? (
                    <ParameterComponent
                      data={data}
                      color={
                        nodeColors[types[data.node.template[field_name].type]] ??
                        nodeColors.unknown
                      }
                      title={
                        data.node.template[field_name].display_name
                          ? data.node.template[field_name].display_name
                          : data.node.template[field_name].name
                            ? toNormalCase(data.node.template[field_name].name)
                            : toNormalCase(field_name)
                      }
                      name={field_name}
                      tooltipTitle={
                        "Type: " +
                        data.node.template[field_name].type +
                        (data.node.template[field_name].list ? " list" : "")
                      }
                      required={data.node.template[field_name].required}
                      id={
                        data.node.template[field_name].type +
                        "|" +
                        field_name +
                        "|" +
                        data.id +
                        (data.node.template[field_name].proxy
                          ? "|" +
                          data.node.template[field_name].proxy.id +
                          "|" +
                          data.node.template[field_name].proxy.field
                          : "")
                      }
                      left={true}
                      type={data.node.template[field_name].type}
                    />
                  ) : (
                    <></>
                  )}
                </div>
              ))}
          </>
          {Object.keys(data.node.template).some(
            (key) => data.node.template[key].root === true
          ) ? (
            Object.keys(data.node.template).map((field_name: string, idx) => {
              if (data.node.template[field_name].root === true)
                return (
                  <InputParameterComponent
                    key={idx}
                    data={data}
                    color={nodeColors[types[data.type]] ?? nodeColors.unknown}
                    title={"Input"}
                    tooltipTitle={`Type: ${data.node.base_classes.join(" | ")}`}
                    id={
                      data.node.template[field_name].type +
                      "|" +
                      field_name +
                      "|" +
                      data.id +
                      (data.node.template[field_name].proxy
                        ? "|" +
                        data.node.template[field_name].proxy.id +
                        "|" +
                        data.node.template[field_name].proxy.field
                        : "")
                    }
                    type={data.node.base_classes.join("|")}
                    left={false}
                  />
                );
            })
          ) : (
            <ParameterComponent
              data={data}
              color={nodeColors[types[data.type]] ?? nodeColors.unknown}
              title={data.type}
              tooltipTitle={`Type: ${data.node.base_classes.join(" | ")}`}
              id={[data.type, data.id, ...data.node.base_classes].join("|")}
              type={data.node.base_classes.join("|")}
              left={false}
            />
          )}
        </div>
      </div>
    </>
  );
}
