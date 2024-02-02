import { useContext, useEffect, useState } from "react";
import { NodeToolbar, useUpdateNodeInternals } from "reactflow";
import ShadTooltip from "../../components/ShadTooltipComponent";
import Tooltip from "../../components/TooltipComponent";
import IconComponent from "../../components/genericIconComponent";
import InputComponent from "../../components/inputComponent";
import { Textarea } from "../../components/ui/textarea";
import { priorityFields } from "../../constants/constants";
import { useSSE } from "../../contexts/SSEContext";
import { alertContext } from "../../contexts/alertContext";
import { FlowsContext } from "../../contexts/flowsContext";
import { typesContext } from "../../contexts/typesContext";
import { undoRedoContext } from "../../contexts/undoRedoContext";
import NodeToolbarComponent from "../../pages/FlowPage/components/nodeToolbarComponent";
import { validationStatusType } from "../../types/components";
import { NodeDataType } from "../../types/flow";
import { handleKeyDown, scapedJSONStringfy } from "../../utils/reactflowUtils";
import { nodeColors, nodeIconsLucide } from "../../utils/styleUtils";
import { classNames, cn, getFieldTitle } from "../../utils/utils";
import ParameterComponent from "./components/parameterComponent";

export default function GenericNode({
  data,
  xPos,
  yPos,
  selected,
}: {
  data: NodeDataType;
  selected: boolean;
  xPos: number;
  yPos: number;
}): JSX.Element {
  const { updateFlow, flows, tabId, saveCurrentFlow } =
    useContext(FlowsContext);
  const updateNodeInternals = useUpdateNodeInternals();
  const { types, deleteNode, reactFlowInstance, setFilterEdge, getFilterEdge } =
    useContext(typesContext);
  const name = nodeIconsLucide[data.type] ? data.type : types[data.type];
  const [inputName, setInputName] = useState(false);
  const [nodeName, setNodeName] = useState(data.node!.display_name);
  const [inputDescription, setInputDescription] = useState(false);
  const [nodeDescription, setNodeDescription] = useState(
    data.node?.description!
  );
  const [validationStatus, setValidationStatus] =
    useState<validationStatusType | null>(null);
  const [handles, setHandles] = useState<boolean[] | []>([]);
  let numberOfInputs: boolean[] = [];
  const { modalContextOpen } = useContext(alertContext);

  const { takeSnapshot } = useContext(undoRedoContext);

  function countHandles(): void {
    numberOfInputs = Object.keys(data.node!.template)
      .filter((templateField) => templateField.charAt(0) !== "_")
      .map((templateCamp) => {
        const { template } = data.node!;
        if (template[templateCamp].input_types) return true;
        if (!template[templateCamp].show) return false;
        switch (template[templateCamp].type) {
          case "str":
            return false;
          case "bool":
            return false;
          case "float":
            return false;
          case "code":
            return false;
          case "prompt":
            return false;
          case "file":
            return false;
          case "int":
            return false;
          default:
            return true;
        }
      });
    setHandles(numberOfInputs);
  }

  useEffect(() => {
    countHandles();
  }, [data, data.node]);

  // State for outline color
  const { sseData, isBuilding } = useSSE();

  useEffect(() => {
    setNodeDescription(data.node!.description);
  }, [data.node!.description]);

  useEffect(() => {
    setNodeName(data.node!.display_name);
  }, [data.node!.display_name]);

  // New useEffect to watch for changes in sseData and update validation status
  useEffect(() => {
    const relevantData = sseData[data.id];
    if (relevantData) {
      // Extract validation information from relevantData and update the validationStatus state
      setValidationStatus(relevantData);
    } else {
      setValidationStatus(null);
    }
  }, [sseData, data.id]);

  const showNode = data.showNode ?? true;

  const nameEditable = data.node?.flow || data.type === "CustomComponent";

  return (
    <>
      <NodeToolbar>
        <NodeToolbarComponent
          position={{ x: xPos, y: yPos }}
          data={data}
          deleteNode={(id) => {
            takeSnapshot();
            deleteNode(id);
            saveCurrentFlow();
          }}
          setShowNode={(show: boolean) => {
            data.showNode = show;
          }}
          numberOfHandles={handles}
          showNode={showNode}
        ></NodeToolbarComponent>
      </NodeToolbar>

      <div
        className={classNames(
          selected ? "border border-ring" : "border",
          showNode ? " w-96 rounded-lg" : " w-26 h-26 rounded-full",
          "generic-node-div"
        )}
      >
        {data.node?.beta && showNode && (
          <div className="beta-badge-wrapper">
            <div className="beta-badge-content">BETA</div>
          </div>
        )}
        <div>
          <div
            data-testid={"div-generic-node"}
            className={
              "generic-node-div-title " +
              (!showNode
                ? " relative h-24 w-24 rounded-full "
                : " justify-between rounded-t-lg ")
            }
          >
            <div
              className={
                "generic-node-title-arrangement rounded-full" +
                (!showNode && "justify-center")
              }
            >
              <IconComponent
                name={data.node?.flow ? "group_components" : name}
                className={
                  "generic-node-icon " +
                  (!showNode ? "absolute inset-x-6 h-12 w-12" : "")
                }
                iconColor={`${nodeColors[types[data.type]]}`}
              />
              {showNode && (
                <div className="generic-node-tooltip-div">
                  {nameEditable && inputName ? (
                    <div>
                      <InputComponent
                        onBlur={() => {
                          setInputName(false);
                          if (nodeName.trim() !== "") {
                            setNodeName(nodeName);
                            data.node!.display_name = nodeName;
                            updateNodeInternals(data.id);
                          } else {
                            setNodeName(data.node!.display_name);
                          }
                        }}
                        value={nodeName}
                        onChange={setNodeName}
                        password={false}
                        blurOnEnter={true}
                      />
                    </div>
                  ) : (
                    <ShadTooltip content={data.node?.display_name}>
                      <div
                        className="flex"
                        onDoubleClick={() => {
                          setInputName(true);
                          takeSnapshot();
                        }}
                      >
                        <div
                          data-testid={"title-" + data.node?.display_name}
                          className="generic-node-tooltip-div pr-2 text-primary"
                        >
                          {data.node?.display_name}
                        </div>
                        {nameEditable && (
                          <IconComponent
                            name="Pencil"
                            className="h-4 w-4 text-ring"
                          />
                        )}
                      </div>
                    </ShadTooltip>
                  )}
                </div>
              )}
            </div>
            <div>
              {!showNode && (
                <>
                  {Object.keys(data.node!.template)
                    .filter((templateField) => templateField.charAt(0) !== "_")
                    .map(
                      (templateField: string, idx) =>
                        data.node!.template[templateField].show &&
                        !data.node!.template[templateField].advanced && (
                          <ParameterComponent
                            index={idx.toString()}
                            key={scapedJSONStringfy({
                              inputTypes:
                                data.node!.template[templateField].input_types,
                              type: data.node!.template[templateField].type,
                              id: data.id,
                              fieldName: templateField,
                              proxy: data.node!.template[templateField].proxy,
                            })}
                            data={data}
                            color={
                              nodeColors[
                                types[data.node?.template[templateField].type!]
                              ] ??
                              nodeColors[
                                data.node?.template[templateField].type!
                              ] ??
                              nodeColors.unknown
                            }
                            title={getFieldTitle(
                              data.node?.template!,
                              templateField
                            )}
                            info={data.node?.template[templateField].info}
                            name={templateField}
                            tooltipTitle={
                              data.node?.template[
                                templateField
                              ].input_types?.join("\n") ??
                              data.node?.template[templateField].type
                            }
                            required={
                              data.node!.template[templateField].required
                            }
                            id={{
                              inputTypes:
                                data.node!.template[templateField].input_types,
                              type: data.node!.template[templateField].type,
                              id: data.id,
                              fieldName: templateField,
                            }}
                            left={true}
                            type={data.node?.template[templateField].type}
                            optionalHandle={
                              data.node?.template[templateField].input_types
                            }
                            proxy={data.node?.template[templateField].proxy}
                            showNode={showNode}
                          />
                        )
                    )}
                  <ParameterComponent
                    key={scapedJSONStringfy({
                      baseClasses: data.node!.base_classes,
                      id: data.id,
                      dataType: data.type,
                    })}
                    data={data}
                    color={nodeColors[types[data.type]] ?? nodeColors.unknown}
                    title={
                      data.node?.output_types &&
                      data.node.output_types.length > 0
                        ? data.node.output_types.join("|")
                        : data.type
                    }
                    tooltipTitle={data.node?.base_classes.join("\n")}
                    id={{
                      baseClasses: data.node!.base_classes,
                      id: data.id,
                      dataType: data.type,
                    }}
                    type={data.node?.base_classes.join("|")}
                    left={false}
                    showNode={showNode}
                  />
                </>
              )}
            </div>

            {showNode && (
              <div className="round-button-div">
                <div>
                  <Tooltip
                    title={
                      isBuilding ? (
                        <span>Building...</span>
                      ) : !validationStatus ? (
                        <span className="flex">
                          Build{" "}
                          <IconComponent
                            name="Zap"
                            className="mx-0.5 h-5 fill-build-trigger stroke-build-trigger stroke-1"
                          />{" "}
                          flow to validate status.
                        </span>
                      ) : (
                        <div className="max-h-96 overflow-auto">
                          {typeof validationStatus.params === "string"
                            ? `Duration: ${validationStatus.duration}\n${validationStatus.params}`
                                .split("\n")
                                .map((line, index) => (
                                  <div key={index}>{line}</div>
                                ))
                            : ""}
                        </div>
                      )
                    }
                  >
                    <div className="generic-node-status-position">
                      <div
                        className={classNames(
                          validationStatus && validationStatus.valid
                            ? "green-status"
                            : "status-build-animation",
                          "status-div"
                        )}
                      ></div>
                      <div
                        className={classNames(
                          validationStatus && !validationStatus.valid
                            ? "red-status"
                            : "status-build-animation",
                          "status-div"
                        )}
                      ></div>
                      <div
                        className={classNames(
                          !validationStatus || isBuilding
                            ? "yellow-status"
                            : "status-build-animation",
                          "status-div"
                        )}
                      ></div>
                    </div>
                  </Tooltip>
                </div>
              </div>
            )}
          </div>
        </div>

        {showNode && (
          <div
            className={
              showNode
                ? data.node?.description === "" && !nameEditable
                  ? "pb-5"
                  : "py-5"
                : ""
            }
          >
            <div className="generic-node-desc">
              {showNode && nameEditable && inputDescription ? (
                <Textarea
                  autoFocus
                  onBlur={() => {
                    setInputDescription(false);
                    setNodeDescription(nodeDescription);
                    data.node!.description = nodeDescription;
                    updateNodeInternals(data.id);
                  }}
                  value={nodeDescription}
                  onChange={(e) => setNodeDescription(e.target.value)}
                  onKeyDown={(e) => {
                    handleKeyDown(e, nodeDescription, "");
                    if (
                      e.key === "Enter" &&
                      e.shiftKey === false &&
                      e.ctrlKey === false &&
                      e.altKey === false
                    ) {
                      setInputDescription(false);
                      setNodeDescription(nodeDescription);
                      data.node!.description = nodeDescription;
                      updateNodeInternals(data.id);
                    }
                  }}
                />
              ) : (
                <div
                  className={cn(
                    "generic-node-desc-text truncate-multiline word-break-break-word",
                    (data.node?.description === "" ||
                      !data.node?.description) &&
                      nameEditable
                      ? "font-light italic"
                      : ""
                  )}
                  onDoubleClick={() => {
                    setInputDescription(true);
                    takeSnapshot();
                  }}
                >
                  {(data.node?.description === "" || !data.node?.description) &&
                  nameEditable
                    ? "Double Click to Edit Description"
                    : data.node?.description}
                </div>
              )}
            </div>
            <>
              {Object.keys(data.node!.template)
                .filter((templateField) => templateField.charAt(0) !== "_")
                .sort((a, b) => {
                  if (priorityFields.has(a.toLowerCase())) {
                    return -1;
                  } else if (priorityFields.has(b.toLowerCase())) {
                    return 1;
                  } else {
                    return a.localeCompare(b);
                  }
                })
                .map((templateField: string, idx) => (
                  <div key={idx}>
                    {data.node!.template[templateField].show &&
                    !data.node!.template[templateField].advanced ? (
                      <ParameterComponent
                        index={idx.toString()}
                        key={scapedJSONStringfy({
                          inputTypes:
                            data.node!.template[templateField].input_types,
                          type: data.node!.template[templateField].type,
                          id: data.id,
                          fieldName: templateField,
                          proxy: data.node!.template[templateField].proxy,
                        })}
                        data={data}
                        color={
                          nodeColors[
                            data.node?.template[templateField].type!
                          ] ??
                          nodeColors[
                            types[data.node?.template[templateField].type!]
                          ] ??
                          nodeColors.unknown
                        }
                        title={getFieldTitle(
                          data.node?.template!,
                          templateField
                        )}
                        info={data.node?.template[templateField].info}
                        name={templateField}
                        tooltipTitle={
                          data.node?.template[templateField].input_types?.join(
                            "\n"
                          ) ?? data.node?.template[templateField].type
                        }
                        required={data.node!.template[templateField].required}
                        id={{
                          inputTypes:
                            data.node!.template[templateField].input_types,
                          type: data.node!.template[templateField].type,
                          id: data.id,
                          fieldName: templateField,
                        }}
                        left={true}
                        type={data.node?.template[templateField].type}
                        optionalHandle={
                          data.node?.template[templateField].input_types
                        }
                        proxy={data.node?.template[templateField].proxy}
                        showNode={showNode}
                      />
                    ) : (
                      <></>
                    )}
                  </div>
                ))}
              <div
                className={classNames(
                  Object.keys(data.node!.template).length < 1 ? "hidden" : "",
                  "flex-max-width justify-center"
                )}
              >
                {" "}
              </div>
              {data.node!.base_classes.length > 0 && (
                <ParameterComponent
                  key={scapedJSONStringfy({
                    baseClasses: data.node!.base_classes,
                    id: data.id,
                    dataType: data.type,
                  })}
                  data={data}
                  color={
                    (data.node?.output_types &&
                    data.node.output_types.length > 0
                      ? nodeColors[data.node.output_types[0]] ??
                        nodeColors[types[data.node.output_types[0]]]
                      : nodeColors[types[data.type]]) ?? nodeColors.unknown
                  }
                  title={
                    data.node?.output_types && data.node.output_types.length > 0
                      ? data.node.output_types.join("|")
                      : data.type
                  }
                  tooltipTitle={data.node?.base_classes.join("\n")}
                  id={{
                    baseClasses: data.node!.base_classes,
                    id: data.id,
                    dataType: data.type,
                  }}
                  type={data.node?.base_classes.join("|")}
                  left={false}
                  showNode={showNode}
                />
              )}
            </>
          </div>
        )}
      </div>
    </>
  );
}
