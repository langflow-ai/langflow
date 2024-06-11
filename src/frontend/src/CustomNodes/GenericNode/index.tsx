import emojiRegex from "emoji-regex";
import { useEffect, useMemo, useState } from "react";
import Markdown from "react-markdown";
import { NodeToolbar, useUpdateNodeInternals } from "reactflow";
import IconComponent from "../../components/genericIconComponent";
import InputComponent from "../../components/inputComponent";
import ShadTooltip from "../../components/shadTooltipComponent";
import { Button } from "../../components/ui/button";
import { Textarea } from "../../components/ui/textarea";
import {
  RUN_TIMESTAMP_PREFIX,
  STATUS_BUILD,
  STATUS_BUILDING,
  TOOLTIP_OUTDATED_NODE,
} from "../../constants/constants";
import { BuildStatus } from "../../constants/enums";
import { postCustomComponent } from "../../controllers/API";
import NodeToolbarComponent from "../../pages/FlowPage/components/nodeToolbarComponent";
import useAlertStore from "../../stores/alertStore";
import { useDarkStore } from "../../stores/darkStore";
import useFlowStore from "../../stores/flowStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { useShortcutsStore } from "../../stores/shortcuts";
import { useTypesStore } from "../../stores/typesStore";
import { VertexBuildTypeAPI } from "../../types/api";
import { NodeDataType } from "../../types/flow";
import { handleKeyDown, scapedJSONStringfy } from "../../utils/reactflowUtils";
import { nodeColors, nodeIconsLucide } from "../../utils/styleUtils";
import { classNames, cn } from "../../utils/utils";
import { countHandlesFn } from "../helpers/count-handles";
import { getSpecificClassFromBuildStatus } from "../helpers/get-class-from-build-status";
import useCheckCodeValidity from "../hooks/use-check-code-validity";
import useIconNodeRender from "../hooks/use-icon-render";
import useIconStatus from "../hooks/use-icons-status";
import useUpdateNodeCode from "../hooks/use-update-node-code";
import useUpdateValidationStatus from "../hooks/use-update-validation-status";
import useValidationStatusString from "../hooks/use-validation-status-string";
import getFieldTitle from "../utils/get-field-title";
import sortFields from "../utils/sort-fields";
import ParameterComponent from "./components/parameterComponent";
import { useHotkeys } from "react-hotkeys-hook";

export default function GenericNode({
  data,

  selected,
}: {
  data: NodeDataType;
  selected: boolean;
  xPos?: number;
  yPos?: number;
}): JSX.Element {
  const preventDefault = true;
  const types = useTypesStore((state) => state.types);
  const templates = useTypesStore((state) => state.templates);
  const deleteNode = useFlowStore((state) => state.deleteNode);
  const flowPool = useFlowStore((state) => state.flowPool);
  const buildFlow = useFlowStore((state) => state.buildFlow);
  const setNode = useFlowStore((state) => state.setNode);
  const updateNodeInternals = useUpdateNodeInternals();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const isDark = useDarkStore((state) => state.dark);
  const buildStatus = useFlowStore(
    (state) => state.flowBuildStatus[data.id]?.status,
  );
  const lastRunTime = useFlowStore(
    (state) => state.flowBuildStatus[data.id]?.timestamp,
  );
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);

  const [inputName, setInputName] = useState(false);
  const [nodeName, setNodeName] = useState(data.node!.display_name);
  const [inputDescription, setInputDescription] = useState(false);
  const [nodeDescription, setNodeDescription] = useState(
    data.node?.description!,
  );
  const [isOutdated, setIsOutdated] = useState(false);
  const [validationStatus, setValidationStatus] =
    useState<VertexBuildTypeAPI | null>(null);
  const [handles, setHandles] = useState<number>(0);
  const [validationString, setValidationString] = useState<string>("");

  const iconStatus = useIconStatus(buildStatus, validationStatus);
  const [showNode, setShowNode] = useState(data.showNode ?? true);
  // State for outline color
  const isBuilding = useFlowStore((state) => state.isBuilding);

  const updateNodeCode = useUpdateNodeCode(
    data?.id,
    data.node!,
    setNode,
    setIsOutdated,
    updateNodeInternals,
  );

  const name = nodeIconsLucide[data.type] ? data.type : types[data.type];

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

  const renderIconStatus = () => {
    return <div className="cursor-help">{iconStatus}</div>;
  };

  const getNodeBorderClassName = (
    selected: boolean,
    showNode: boolean,
    buildStatus: BuildStatus | undefined,
    validationStatus: VertexBuildTypeAPI | null,
  ) => {
    const specificClassFromBuildStatus = getSpecificClassFromBuildStatus(
      buildStatus,
      validationStatus,
      isDark,
    );

    const baseBorderClass = getBaseBorderClass(selected);
    const nodeSizeClass = getNodeSizeClass(showNode);
    const names = classNames(
      baseBorderClass,
      nodeSizeClass,
      "generic-node-div group/node",
      specificClassFromBuildStatus,
    );
    return names;
  };

  //  const [openWDoubleCLick, setOpenWDoubleCLick] = useState(false);

  const getBaseBorderClass = (selected) => {
    let className = selected
      ? "border border-ring hover:shadow-node"
      : "border hover:shadow-node";
    let frozenClass = selected ? "border-ring-frozen" : "border-frozen";
    return data.node?.frozen ? frozenClass : className;
  };

  const getNodeSizeClass = (showNode) =>
    showNode ? "w-96 rounded-lg" : "w-26 h-26 rounded-full";

  const nameEditable = true;
  const isEmoji = emojiRegex().test(data?.node?.icon!);

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

  useCheckCodeValidity(data, templates, setIsOutdated, types);
  useValidationStatusString(validationStatus, setValidationString);
  useUpdateValidationStatus(data?.id, flowPool, setValidationStatus);

  const iconNodeRender = useIconNodeRender(
    data,
    types,
    nodeColors,
    name,
    showNode,
    isEmoji,
    nodeIconFragment,
    checkNodeIconFragment,
  );

  function countHandles(): void {
    const count = countHandlesFn(data);
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

  useEffect(() => {
    setNodeDescription(data.node!.description);
  }, [data.node!.description]);

  useEffect(() => {
    setNodeName(data.node!.display_name);
  }, [data.node!.display_name]);

  useEffect(() => {
    setShowNode(data.showNode ?? true);
  }, [data.showNode]);

  const [loadingUpdate, setLoadingUpdate] = useState(false);

  const handleUpdateCode = () => {
    setLoadingUpdate(true);
    takeSnapshot();
    // to update we must get the code from the templates in useTypesStore
    const thisNodeTemplate = templates[data.type]?.template;
    // if the template does not have a code key
    // return
    if (!thisNodeTemplate?.code) return;

    const currentCode = thisNodeTemplate.code.value;
    if (data.node) {
      postCustomComponent(currentCode, data.node)
        .then((apiReturn) => {
          const { data } = apiReturn;
          if (data && updateNodeCode) {
            updateNodeCode(data, currentCode, "code");
            setLoadingUpdate(false);
          }
        })
        .catch((err) => {
          console.log(err);
        });
    }
  };

  function handleUpdateCodeWShortcut() {
    if (isOutdated && selected) {
      handleUpdateCode();
    }
  }

  function handlePlayWShortcut() {
    if (buildStatus === BuildStatus.BUILDING || isBuilding || !selected) return;
    setValidationStatus(null);
    console.log(data.node?.display_name);
    buildFlow({ stopNodeId: data.id });
  }

  const update = useShortcutsStore((state) => state.update);
  const play = useShortcutsStore((state) => state.play);

  useHotkeys(update, handleUpdateCodeWShortcut, { preventDefault });
  useHotkeys(play, handlePlayWShortcut, { preventDefault });

  const shortcuts = useShortcutsStore((state) => state.shortcuts);

  const memoizedNodeToolbarComponent = useMemo(() => {
    return (
      <NodeToolbar>
        <NodeToolbarComponent
          //          openWDoubleClick={openWDoubleCLick}
          //          setOpenWDoubleClick={setOpenWDoubleCLick}
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
          selected={selected}
          updateNode={handleUpdateCode}
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
    shortcuts,
    //    openWDoubleCLick,
    //    setOpenWDoubleCLick,
  ]);
  return (
    <>
      {memoizedNodeToolbarComponent}
      <div
        //        onDoubleClick={(event) => {
        //          if (!isWrappedWithClass(event, "nodoubleclick"))
        //            setOpenWDoubleCLick(true);
        //        }}
        className={getNodeBorderClassName(
          selected,
          showNode,
          buildStatus,
          validationStatus,
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
              data-testid="generic-node-title-arrangement"
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
                    <div className="group flex items-center gap-1">
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
                          className="nodoubleclick generic-node-tooltip-div cursor-text text-primary"
                        >
                          {data.node?.display_name}
                        </div>
                      </ShadTooltip>
                      {isOutdated && (
                        <ShadTooltip content={TOOLTIP_OUTDATED_NODE}>
                          <Button
                            onClick={handleUpdateCode}
                            variant="none"
                            size="none"
                            className={"group p-1"}
                            loading={loadingUpdate}
                          >
                            <IconComponent
                              name="AlertTriangle"
                              className="h-5 w-5 fill-status-yellow text-muted"
                            />
                          </Button>
                        </ShadTooltip>
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
                            selected={selected}
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
                              templateField,
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
                        ),
                    )}
                  <ParameterComponent
                    selected={selected}
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
              <>
                <div className="flex flex-shrink-0 items-center gap-2">
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
                            <div className="ml-1 text-status-blue">
                              {validationStatus?.data.duration}
                            </div>
                          </div>
                        </div>
                      )
                    }
                    side="bottom"
                  >
                    {renderIconStatus()}
                  </ShadTooltip>
                  <Button
                    onClick={() => {
                      if (buildStatus === BuildStatus.BUILDING || isBuilding)
                        return;
                      setValidationStatus(null);
                      buildFlow({ stopNodeId: data.id });
                    }}
                    variant="none"
                    size="none"
                    className="group p-1"
                  >
                    <div
                      data-testid={
                        `button_run_` + data?.node?.display_name.toLowerCase()
                      }
                    >
                      <IconComponent
                        name="Play"
                        className={
                          "h-5 w-5 fill-current stroke-2 text-muted-foreground transition-all group-hover:text-medium-indigo group-hover/node:opacity-100"
                        }
                      />
                    </div>
                  </Button>
                </div>
              </>
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
            {/* increase height!! */}
            <div className="generic-node-desc">
              {showNode && nameEditable && inputDescription ? (
                <Textarea
                  className="nowheel min-h-40"
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
                    "nodoubleclick generic-node-desc-text cursor-text word-break-break-word",
                    (data.node?.description === "" ||
                      !data.node?.description) &&
                      nameEditable
                      ? "font-light italic"
                      : "",
                  )}
                  onDoubleClick={(e) => {
                    setInputDescription(true);
                    takeSnapshot();
                  }}
                >
                  {(data.node?.description === "" || !data.node?.description) &&
                  nameEditable ? (
                    "Double Click to Edit Description"
                  ) : (
                    <Markdown
                      className="markdown prose flex flex-col text-primary word-break-break-word
    dark:prose-invert"
                    >
                      {String(data.node?.description)}
                    </Markdown>
                  )}
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
                        selected={selected}
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
                          templateField,
                        )}
                        info={data.node?.template[templateField].info}
                        name={templateField}
                        tooltipTitle={
                          data.node?.template[templateField].input_types?.join(
                            "\n",
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
                  "flex-max-width justify-center",
                )}
              >
                {" "}
              </div>
              {data.node!.base_classes.length > 0 && (
                <ParameterComponent
                  selected={selected}
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
