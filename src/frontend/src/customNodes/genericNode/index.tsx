import { cloneDeep } from "lodash";
import { useCallback, useEffect, useMemo, useState } from "react";
import { NodeToolbar, useUpdateNodeInternals } from "reactflow";
import IconComponent from "../../components/genericIconComponent";
import InputComponent from "../../components/inputComponent";
import ShadTooltip from "../../components/shadTooltipComponent";
import { Button } from "../../components/ui/button";
import Checkmark from "../../components/ui/checkmark";
import Loading from "../../components/ui/loading";
import { Textarea } from "../../components/ui/textarea";
import Xmark from "../../components/ui/xmark";
import {
  NATIVE_CATEGORIES,
  RUN_TIMESTAMP_PREFIX,
  STATUS_BUILD,
  STATUS_BUILDING,
} from "../../constants/constants";
import { BuildStatus } from "../../constants/enums";
import NodeToolbarComponent from "../../pages/FlowPage/components/nodeToolbarComponent";
import useAlertStore from "../../stores/alertStore";
import { useDarkStore } from "../../stores/darkStore";
import useFlowStore from "../../stores/flowStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { useTypesStore } from "../../stores/typesStore";
import { APIClassType } from "../../types/api";
import { validationStatusType } from "../../types/components";
import { NodeDataType } from "../../types/flow";
import { handleKeyDown, scapedJSONStringfy } from "../../utils/reactflowUtils";
import { nodeColors, nodeIconsLucide } from "../../utils/styleUtils";
import { classNames, cn, getFieldTitle, sortFields } from "../../utils/utils";
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
  const types = useTypesStore((state) => state.types);
  const templates = useTypesStore((state) => state.templates);
  const deleteNode = useFlowStore((state) => state.deleteNode);
  const flowPool = useFlowStore((state) => state.flowPool);
  const buildFlow = useFlowStore((state) => state.buildFlow);
  const setNode = useFlowStore((state) => state.setNode);
  const updateNodeInternals = useUpdateNodeInternals();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const name = nodeIconsLucide[data.type] ? data.type : types[data.type];
  const [inputName, setInputName] = useState(false);
  const [nodeName, setNodeName] = useState(data.node!.display_name);
  const [inputDescription, setInputDescription] = useState(false);
  const [nodeDescription, setNodeDescription] = useState(
    data.node?.description!
  );
  const [isOutdated, setIsOutdated] = useState(false);
  const buildStatus = useFlowStore(
    (state) => state.flowBuildStatus[data.id]?.status
  );
  const lastRunTime = useFlowStore(
    (state) => state.flowBuildStatus[data.id]?.timestamp
  );
  const [validationStatus, setValidationStatus] =
    useState<validationStatusType | null>(null);
  const [handles, setHandles] = useState<number>(0);

  const [validationString, setValidationString] = useState<string>("");

  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);

  useEffect(() => {
    // This one should run only once
    // first check if data.type in NATIVE_CATEGORIES
    // if not return
    if (
      !NATIVE_CATEGORIES.includes(types[data.type]) ||
      !data.node?.template?.code?.value
    )
      return;
    const thisNodeTemplate = templates[data.type].template;
    // if the template does not have a code key
    // return
    if (!thisNodeTemplate.code) return;
    const currentCode = thisNodeTemplate.code?.value;
    const thisNodesCode = data.node!.template?.code?.value;
    const componentsToIgnore = ["Custom Component", "Prompt"];
    if (
      currentCode !== thisNodesCode &&
      !componentsToIgnore.includes(data.node!.display_name)
    ) {
      setIsOutdated(true);
    } else {
      setIsOutdated(false);
    }
    // template.code can be undefined
  }, [data.node?.template?.code?.value]);

  const updateNodeCode = useCallback(
    (newNodeClass: APIClassType, code: string, name: string) => {
      setNode(data.id, (oldNode) => {
        let newNode = cloneDeep(oldNode);

        newNode.data = {
          ...newNode.data,
          node: newNodeClass,
          description: newNodeClass.description ?? data.node!.description,
          display_name: newNodeClass.display_name ?? data.node!.display_name,
        };

        newNode.data.node.template[name].value = code;
        setIsOutdated(false);

        return newNode;
      });

      updateNodeInternals(data.id);
    },
    [data.id, data.node, setNode, setIsOutdated]
  );

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

  function countHandles(): void {
    let count = Object.keys(data.node!.template)
      .filter((templateField) => templateField.charAt(0) !== "_")
      .map((templateCamp) => {
        const { template } = data.node!;
        if (template[templateCamp].input_types) return true;
        if (!template[templateCamp].show) return false;
        switch (template[templateCamp].type) {
          case "str":
          case "bool":
          case "float":
          case "code":
          case "prompt":
          case "file":
          case "int":
            return false;
          default:
            return true;
        }
      })
      .reduce((total, value) => total + (value ? 1 : 0), 0);

    setHandles(count);
  }
  useEffect(() => {
    countHandles();
  }, [data, data.node]);

  useEffect(() => {
    if (!selected) {
      setInputName(false);
      setInputDescription(false);
    }
  }, [selected]);

  // State for outline color
  const isBuilding = useFlowStore((state) => state.isBuilding);

  // should be empty string if no duration
  // else should be `Duration: ${duration}`
  const getDurationString = (duration: number | undefined): string => {
    if (duration === undefined) {
      return "";
    } else {
      return `${duration}`;
    }
  };
  const durationString = getDurationString(validationStatus?.data.duration);

  useEffect(() => {
    setNodeDescription(data.node!.description);
  }, [data.node!.description]);

  useEffect(() => {
    setNodeName(data.node!.display_name);
  }, [data.node!.display_name]);

  useEffect(() => {
    const relevantData =
      flowPool[data.id] && flowPool[data.id]?.length > 0
        ? flowPool[data.id][flowPool[data.id].length - 1]
        : null;
    if (relevantData) {
      // Extract validation information from relevantData and update the validationStatus state
      setValidationStatus(relevantData);
    } else {
      setValidationStatus(null);
    }
  }, [flowPool[data.id], data.id]);

  useEffect(() => {
    if (validationStatus?.params) {
      // if it is not a string turn it into a string
      let newValidationString = validationStatus.params;
      if (typeof newValidationString !== "string") {
        newValidationString = JSON.stringify(validationStatus.params);
      }

      setValidationString(newValidationString);
    }
  }, [validationStatus, validationStatus?.params]);

  const [showNode, setShowNode] = useState(data.showNode ?? true);

  useEffect(() => {
    setShowNode(data.showNode ?? true);
  }, [data.showNode]);

  const nameEditable = true;

  const emojiRegex = /\p{Emoji}/u;
  const isEmoji = emojiRegex.test(data?.node?.icon!);

  const iconNodeRender = useCallback(() => {
    const iconElement = data?.node?.icon;
    const iconColor = nodeColors[types[data.type]];
    const iconName =
      iconElement || (data.node?.flow ? "group_components" : name);
    const iconClassName = `generic-node-icon ${
      !showNode ? " absolute inset-x-6 h-12 w-12 " : ""
    }`;
    if (iconElement && isEmoji) {
      return nodeIconFragment(iconElement);
    } else {
      return checkNodeIconFragment(iconColor, iconName, iconClassName);
    }
  }, [data, isEmoji, name, showNode]);

  const nodeIconFragment = (icon) => {
    return <span className="text-lg">{icon}</span>;
  };

  const checkNodeIconFragment = (iconColor, iconName, iconClassName) => {
    return (
      <IconComponent
        name={iconName}
        className={iconClassName}
        iconColor={iconColor}
      />
    );
  };

  const isDark = useDarkStore((state) => state.dark);
  const renderIconStatus = (
    buildStatus: BuildStatus | undefined,
    validationStatus: validationStatusType | null
  ) => {
    if (buildStatus === BuildStatus.BUILDING) {
      return <Loading className="text-medium-indigo" />;
    } else {
      return (
        <>
          <IconComponent
            name="Play"
            className="absolute ml-0.5 h-5 fill-current stroke-2 text-medium-indigo opacity-0 transition-all group-hover:opacity-100"
          />
          {validationStatus && validationStatus.valid ? (
            <Checkmark
              className="absolute ml-0.5 h-5 stroke-2 text-status-green opacity-100 transition-all group-hover:opacity-0"
              isVisible={true}
            />
          ) : validationStatus &&
            !validationStatus.valid &&
            buildStatus === BuildStatus.INACTIVE ? (
            <IconComponent
              name="Play"
              className="absolute ml-0.5 h-5 fill-current stroke-2 text-status-green opacity-30 transition-all group-hover:opacity-0"
            />
          ) : buildStatus === BuildStatus.ERROR ||
            (validationStatus && !validationStatus.valid) ? (
            <Xmark
              isVisible={true}
              className="absolute ml-0.5 h-5 fill-current stroke-2 text-status-red opacity-100 transition-all group-hover:opacity-0"
            />
          ) : (
            <IconComponent
              name="Play"
              className="absolute ml-0.5 h-5 fill-current stroke-2 text-muted-foreground opacity-100 transition-all group-hover:opacity-0"
            />
          )}
        </>
      );
    }
  };
  const getSpecificClassFromBuildStatus = (
    buildStatus: BuildStatus | undefined,
    validationStatus: validationStatusType | null
  ) => {
    let isInvalid = validationStatus && !validationStatus.valid;

    if (buildStatus === BuildStatus.INACTIVE && isInvalid) {
      // INACTIVE should have its own class
      return "inactive-status";
    }
    if (
      (buildStatus === BuildStatus.BUILT && isInvalid) ||
      buildStatus === BuildStatus.ERROR
    ) {
      return isDark ? "built-invalid-status-dark" : "built-invalid-status";
    } else if (buildStatus === BuildStatus.BUILDING) {
      return "building-status";
    } else {
      return "";
    }
  };

  const getNodeBorderClassName = (
    selected: boolean,
    showNode: boolean,
    buildStatus: BuildStatus | undefined,
    validationStatus: validationStatusType | null
  ) => {
    const specificClassFromBuildStatus = getSpecificClassFromBuildStatus(
      buildStatus,
      validationStatus
    );
    const baseBorderClass = getBaseBorderClass(selected);
    const nodeSizeClass = getNodeSizeClass(showNode);
    return classNames(
      baseBorderClass,
      nodeSizeClass,
      "generic-node-div",
      specificClassFromBuildStatus
    );
  };

  const getBaseBorderClass = (selected) =>
    selected ? "border border-ring" : "border";

  const getNodeSizeClass = (showNode) =>
    showNode ? "w-96 rounded-lg" : "w-26 h-26 rounded-full";

  const memoizedNodeToolbarComponent = useMemo(() => {
    return (
      <NodeToolbar>
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
          setShowState={setShowNode}
          numberOfHandles={handles}
          showNode={showNode}
          openAdvancedModal={false}
          onCloseAdvancedModal={() => {}}
          updateNodeCode={updateNodeCode}
          isOutdated={isOutdated}
          selected={selected}
        />
      </NodeToolbar>
    );
  }, [
    data,
    deleteNode,
    takeSnapshot,
    setNode,
    setShowNode,
    handles,
    showNode,
    updateNodeCode,
    isOutdated,
    selected,
  ]);

  return (
    <>
      {memoizedNodeToolbarComponent}
      <div
        className={getNodeBorderClassName(
          selected,
          showNode,
          buildStatus,
          validationStatus
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
                (!showNode && " justify-center ")
              }
            >
              {iconNodeRender()}
              {showNode && (
                <div className="generic-node-tooltip-div">
                  {nameEditable && inputName ? (
                    <div>
                      <InputComponent
                        onBlur={() => {
                          setInputName(false);
                          if (nodeName.trim() !== "") {
                            setNodeName(nodeName);
                            setNode(data.id, (old) => ({
                              ...old,
                              data: {
                                ...old.data,
                                node: {
                                  ...old.data.node,
                                  display_name: nodeName,
                                },
                              },
                            }));
                          } else {
                            setNodeName(data.node!.display_name);
                          }
                        }}
                        value={nodeName}
                        onChange={setNodeName}
                        password={false}
                        blurOnEnter={true}
                        id={`input-title-${data.node?.display_name}`}
                      />
                    </div>
                  ) : (
                    <div className="group flex items-start gap-1.5">
                      <ShadTooltip content={data.node?.display_name}>
                        <div
                          onDoubleClick={(event) => {
                            if (nameEditable) {
                              setInputName(true);
                            }
                            takeSnapshot();
                            event.stopPropagation();
                            event.preventDefault();
                          }}
                          data-testid={"title-" + data.node?.display_name}
                          className="generic-node-tooltip-div cursor-text text-primary"
                        >
                          {data.node?.display_name}
                        </div>
                      </ShadTooltip>
                      {nameEditable && (
                        <div
                          onClick={(event) => {
                            setInputName(true);
                            takeSnapshot();
                            event.stopPropagation();
                            event.preventDefault();
                          }}
                        >
                          <IconComponent
                            name="PencilLine"
                            className="hidden h-3 w-3 text-status-blue group-hover:block"
                          />
                        </div>
                      )}
                    </div>
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
                              data.node?.template[templateField].input_types &&
                              data.node?.template[templateField].input_types!
                                .length > 0
                                ? nodeColors[
                                    data.node?.template[templateField]
                                      .input_types![
                                      data.node?.template[templateField]
                                        .input_types!.length - 1
                                    ]
                                  ] ??
                                  nodeColors[
                                    types[
                                      data.node?.template[templateField]
                                        .input_types![
                                        data.node?.template[templateField]
                                          .input_types!.length - 1
                                      ]
                                    ]
                                  ]
                                : nodeColors[
                                    data.node?.template[templateField].type!
                                  ] ??
                                  nodeColors[
                                    types[
                                      data.node?.template[templateField].type!
                                    ]
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
                        ? data.node.output_types.join(" | ")
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
              <ShadTooltip
                content={
                  buildStatus === BuildStatus.BUILDING ? (
                    <span> {STATUS_BUILDING} </span>
                  ) : !validationStatus ? (
                    <span className="flex">{STATUS_BUILD}</span>
                  ) : (
                    <div className="max-h-100 p-2">
                      <div>
                        {lastRunTime && (
                          <div className="justify-left flex font-normal text-muted-foreground">
                            <div>{RUN_TIMESTAMP_PREFIX}</div>
                            <div className="ml-1 text-status-blue">
                              {lastRunTime}
                            </div>
                          </div>
                        )}
                      </div>
                      <div className="justify-left flex font-normal text-muted-foreground">
                        <div>Duration:</div>
                        <div className="mb-3 ml-1 text-status-blue">
                          {validationStatus?.data.duration}
                        </div>
                      </div>
                      <hr />
                      <span className="mb-2 mt-2   flex justify-center font-semibold text-muted-foreground">
                        Output
                      </span>
                      <div className="max-h-96 overflow-auto font-normal custom-scroll">
                        {validationString.split("\n").map((line, index) => (
                          <div className="font-normal" key={index}>
                            {line}
                          </div>
                        ))}
                      </div>
                    </div>
                  )
                }
                side="bottom"
              >
                <Button
                  onClick={() => {
                    if (buildStatus === BuildStatus.BUILDING || isBuilding)
                      return;
                    setValidationStatus(null);
                    buildFlow({ stopNodeId: data.id });
                  }}
                  variant="secondary"
                  className={"group h-9 px-1.5"}
                >
                  <div
                    data-testid={
                      `button_run_` + data?.node?.display_name.toLowerCase()
                    }
                  >
                    <div className="generic-node-status-position flex items-center justify-center">
                      {renderIconStatus(buildStatus, validationStatus)}
                    </div>
                  </div>
                </Button>
              </ShadTooltip>
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
                    setInputName(false);
                    setNodeDescription(nodeDescription);
                    setNode(data.id, (old) => ({
                      ...old,
                      data: {
                        ...old.data,
                        node: {
                          ...old.data.node,
                          description: nodeDescription,
                        },
                      },
                    }));
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
                      setNode(data.id, (old) => ({
                        ...old,
                        data: {
                          ...old.data,
                          node: {
                            ...old.data.node,
                            description: nodeDescription,
                          },
                        },
                      }));
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
                  onDoubleClick={(e) => {
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
                .sort((a, b) => sortFields(a, b, data.node?.field_order ?? []))
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
                          data.node?.template[templateField].input_types &&
                          data.node?.template[templateField].input_types!
                            .length > 0
                            ? nodeColors[
                                data.node?.template[templateField].input_types![
                                  data.node?.template[templateField]
                                    .input_types!.length - 1
                                ]
                              ] ??
                              nodeColors[
                                types[
                                  data.node?.template[templateField]
                                    .input_types![
                                    data.node?.template[templateField]
                                      .input_types!.length - 1
                                  ]
                                ]
                              ]
                            : nodeColors[
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
                      ? data.node.output_types.join(" | ")
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
