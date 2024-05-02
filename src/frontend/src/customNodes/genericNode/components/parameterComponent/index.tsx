import { cloneDeep } from "lodash";
import React, { ReactNode, useEffect, useRef, useState } from "react";
import { Handle, Position, useUpdateNodeInternals } from "reactflow";
import CodeAreaComponent from "../../../../components/codeAreaComponent";
import DictComponent from "../../../../components/dictComponent";
import Dropdown from "../../../../components/dropdownComponent";
import FloatComponent from "../../../../components/floatComponent";
import { default as IconComponent } from "../../../../components/genericIconComponent";
import InputFileComponent from "../../../../components/inputFileComponent";
import InputGlobalComponent from "../../../../components/inputGlobalComponent";
import InputListComponent from "../../../../components/inputListComponent";
import IntComponent from "../../../../components/intComponent";
import KeypairListComponent from "../../../../components/keypairListComponent";
import PromptAreaComponent from "../../../../components/promptComponent";
import ShadTooltip from "../../../../components/shadTooltipComponent";
import TextAreaComponent from "../../../../components/textAreaComponent";
import ToggleShadComponent from "../../../../components/toggleShadComponent";
import { Button } from "../../../../components/ui/button";
import { RefreshButton } from "../../../../components/ui/refreshButton";
import {
  INPUT_HANDLER_HOVER,
  LANGFLOW_SUPPORTED_TYPES,
  OUTPUT_HANDLER_HOVER,
  TOOLTIP_EMPTY,
} from "../../../../constants/constants";
import useAlertStore from "../../../../stores/alertStore";
import useFlowStore from "../../../../stores/flowStore";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { useTypesStore } from "../../../../stores/typesStore";
import {
  APIClassType,
  ResponseErrorDetailAPI,
  ResponseErrorTypeAPI,
} from "../../../../types/api";
import { ParameterComponentType } from "../../../../types/components";
import {
  debouncedHandleUpdateValues,
  handleUpdateValues,
} from "../../../../utils/parameterUtils";
import {
  convertObjToArray,
  convertValuesToNumbers,
  hasDuplicateKeys,
  isValidConnection,
  scapedJSONStringfy,
} from "../../../../utils/reactflowUtils";
import {
  nodeColors,
  nodeIconsLucide,
  nodeNames,
} from "../../../../utils/styleUtils";
import { classNames, groupByFamily } from "../../../../utils/utils";

export default function ParameterComponent({
  left,
  id,
  data,
  tooltipTitle,
  title,
  color,
  type,
  name = "",
  required = false,
  optionalHandle = null,
  info = "",
  proxy,
  showNode,
  index = "",
}: ParameterComponentType): JSX.Element {
  const ref = useRef<HTMLDivElement>(null);
  const refHtml = useRef<HTMLDivElement & ReactNode>(null);
  const infoHtml = useRef<HTMLDivElement & ReactNode>(null);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  const nodes = useFlowStore((state) => state.nodes);
  const edges = useFlowStore((state) => state.edges);
  const setNode = useFlowStore((state) => state.setNode);

  const [isLoading, setIsLoading] = useState(false);
  const flow = currentFlow?.data?.nodes ?? null;

  const groupedEdge = useRef(null);

  const setFilterEdge = useFlowStore((state) => state.setFilterEdge);

  let disabled =
    edges.some(
      (edge) =>
        edge.targetHandle === scapedJSONStringfy(proxy ? { ...id, proxy } : id)
    ) ?? false;

  const myData = useTypesStore((state) => state.data);

  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);

  const handleRefreshButtonPress = async (name, data) => {
    setIsLoading(true);
    try {
      let newTemplate = await handleUpdateValues(name, data);
      if (newTemplate) {
        setNode(data.id, (oldNode) => {
          let newNode = cloneDeep(oldNode);
          newNode.data = {
            ...newNode.data,
          };
          newNode.data.node.template = newTemplate;
          return newNode;
        });
      }
    } catch (error) {
      let responseError = error as ResponseErrorDetailAPI;

      setErrorData({
        title: "Error while updating the Component",
        list: [responseError.response.data.detail ?? "Unknown error"],
      });
    }
    setIsLoading(false);
    renderTooltips();
  };

  useEffect(() => {
    async function fetchData() {
      if (
        (data.node?.template[name]?.real_time_refresh ||
          data.node?.template[name]?.refresh_button) &&
        // options can be undefined but not an empty array
        (data.node?.template[name]?.options?.length ?? 0) === 0
      ) {
        setIsLoading(true);
        try {
          let newTemplate = await handleUpdateValues(name, data);
          if (newTemplate) {
            setNode(data.id, (oldNode) => {
              let newNode = cloneDeep(oldNode);
              newNode.data = {
                ...newNode.data,
              };
              newNode.data.node.template = newTemplate;
              return newNode;
            });
          }
        } catch (error) {
          let responseError = error as ResponseErrorDetailAPI;

          setErrorData({
            title: "Error while updating the Component",
            list: [responseError.response.data.detail ?? "Unknown error"],
          });
        }
        setIsLoading(false);
        renderTooltips();
      }
    }
    fetchData();
  }, []);
  const handleOnNewValue = async (
    newValue: string | string[] | boolean | Object[]
  ): Promise<void> => {
    if (data.node!.template[name].value !== newValue) {
      takeSnapshot();
    }
    const shouldUpdate =
      data.node?.template[name].real_time_refresh &&
      !data.node?.template[name].refresh_button &&
      data.node!.template[name].value !== newValue;

    data.node!.template[name].value = newValue; // necessary to enable ctrl+z inside the input
    let newTemplate;
    if (shouldUpdate) {
      setIsLoading(true);
      try {
        newTemplate = await debouncedHandleUpdateValues(name, data);
      } catch (error) {
        let responseError = error as ResponseErrorTypeAPI;
        setErrorData({
          title: "Error while updating the Component",
          list: [responseError.response.data.detail.error ?? "Unknown error"],
        });
      }
      setIsLoading(false);
      // this de
    }
    setNode(data.id, (oldNode) => {
      let newNode = cloneDeep(oldNode);

      newNode.data = {
        ...newNode.data,
      };

      if (data.node?.template[name].real_time_refresh && newTemplate) {
        newNode.data.node.template = newTemplate;
      } else newNode.data.node.template[name].value = newValue;

      return newNode;
    });

    renderTooltips();
  };

  const updateNodeInternals = useUpdateNodeInternals();

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

    renderTooltips();
  };

  const [errorDuplicateKey, setErrorDuplicateKey] = useState(false);

  useEffect(() => {
    // @ts-ignore
    infoHtml.current = (
      <div className="h-full w-full break-words">
        {info.split("\n").map((line, index) => (
          <p key={index} className="block">
            {line}
          </p>
        ))}
      </div>
    );
  }, [info]);

  function renderTooltips() {
    let groupedObj: any = groupByFamily(myData, tooltipTitle!, left, flow!);
    groupedEdge.current = groupedObj;

    if (groupedObj && groupedObj.length > 0) {
      //@ts-ignore
      refHtml.current = groupedObj.map((item, index) => {
        const Icon: any =
          nodeIconsLucide[item.family] ?? nodeIconsLucide["unknown"];

        return (
          <div
            key={index}
            data-testid={`available-${left ? "input" : "output"}-${
              item.family
            }`}
          >
            {index === 0 && (
              <span>{left ? INPUT_HANDLER_HOVER : OUTPUT_HANDLER_HOVER}</span>
            )}
            <span
              key={index}
              className={classNames(
                index > 0 ? "mt-2 flex items-center" : "mt-3 flex items-center"
              )}
            >
              <div
                className="h-5 w-5"
                style={{
                  color: nodeColors[item.family],
                }}
              >
                <Icon
                  className="h-5 w-5"
                  strokeWidth={1.5}
                  style={{
                    color: nodeColors[item.family] ?? nodeColors.unknown,
                  }}
                />
              </div>
              <span
                className="ps-2 text-xs text-foreground"
                data-testid={`tooltip-${nodeNames[item.family] ?? "Other"}`}
              >
                {nodeNames[item.family] ?? "Other"}{" "}
                {item?.display_name && item?.display_name?.length > 0 ? (
                  <span
                    className="text-xs"
                    data-testid={`tooltip-${item?.display_name}`}
                  >
                    {" "}
                    {item.display_name === "" ? "" : " - "}
                    {item.display_name.split(", ").length > 2
                      ? item.display_name.split(", ").map((el, index) => (
                          <React.Fragment key={el + name}>
                            <span>
                              {index ===
                              item.display_name.split(", ").length - 1
                                ? el
                                : (el += `, `)}
                            </span>
                          </React.Fragment>
                        ))
                      : item.display_name}
                  </span>
                ) : (
                  <span
                    className="text-xs"
                    data-testid={`tooltip-${item?.type}`}
                  >
                    {" "}
                    {item.type === "" ? "" : " - "}
                    {item.type.split(", ").length > 2
                      ? item.type.split(", ").map((el, index) => (
                          <React.Fragment key={el + name}>
                            <span>
                              {index === item.type.split(", ").length - 1
                                ? el
                                : (el += `, `)}
                            </span>
                          </React.Fragment>
                        ))
                      : item.type}
                  </span>
                )}
              </span>
            </span>
          </div>
        );
      });
    } else {
      //@ts-ignore
      refHtml.current = (
        <span data-testid={`empty-tooltip-filter`}>{TOOLTIP_EMPTY}</span>
      );
    }
  }
  // If optionalHandle is an empty list, then it is not an optional handle
  if (optionalHandle && optionalHandle.length === 0) {
    optionalHandle = null;
  }

  useEffect(() => {
    renderTooltips();
  }, [tooltipTitle, flow]);
  return !showNode ? (
    left && LANGFLOW_SUPPORTED_TYPES.has(type ?? "") && !optionalHandle ? (
      <></>
    ) : (
      <Button className="h-7 truncate bg-muted p-0 text-sm font-normal text-black hover:bg-muted">
        <div className="flex">
          <ShadTooltip
            styleClasses={"tooltip-fixed-width custom-scroll nowheel"}
            delayDuration={1000}
            content={refHtml.current}
            side={left ? "left" : "right"}
          >
            <Handle
              data-test-id={`handle-${title.toLowerCase()}-${
                left ? "target" : "source"
              }`}
              type={left ? "target" : "source"}
              position={left ? Position.Left : Position.Right}
              key={
                proxy
                  ? scapedJSONStringfy({ ...id, proxy })
                  : scapedJSONStringfy(id)
              }
              id={
                proxy
                  ? scapedJSONStringfy({ ...id, proxy })
                  : scapedJSONStringfy(id)
              }
              isValidConnection={(connection) =>
                isValidConnection(connection, nodes, edges)
              }
              className={classNames(
                left ? "my-12 -ml-0.5 " : " my-12 -mr-0.5 ",
                "h-3 w-3 rounded-full border-2 bg-background",
                !showNode ? "mt-0" : ""
              )}
              style={{
                borderColor: color ?? nodeColors.unknown,
              }}
              onClick={() => {
                setFilterEdge(groupedEdge.current);
              }}
            ></Handle>
          </ShadTooltip>
        </div>
      </Button>
    )
  ) : (
    <div
      ref={ref}
      className={
        "relative mt-1 flex w-full flex-wrap items-center justify-between bg-muted px-5 py-2" +
        ((name === "code" && type === "code") ||
        (name.includes("code") && proxy)
          ? " hidden "
          : "")
      }
    >
      <>
        <div
          className={
            "flex w-full items-center truncate text-sm" +
            (left ? "" : " justify-end")
          }
        >
          {!left && data.node?.frozen && (
            <div className="pr-1">
              <IconComponent className="h-5 w-5 text-ice" name={"Snowflake"} />
            </div>
          )}
          {proxy ? (
            <ShadTooltip content={<span>{proxy.id}</span>}>
              <span className={!left && data.node?.frozen ? " text-ice" : ""}>
                {title}
              </span>
            </ShadTooltip>
          ) : (
            <span className={!left && data.node?.frozen ? " text-ice" : ""}>
              {title}
            </span>
          )}
          <span className={(required ? "ml-2 " : "") + "text-status-red"}>
            {required ? "*" : ""}
          </span>
          <div className="">
            {info !== "" && (
              <ShadTooltip content={infoHtml.current}>
                {/* put div to avoid bug that does not display tooltip */}
                <div>
                  <IconComponent
                    name="Info"
                    className="relative bottom-px ml-1.5 h-3 w-4"
                  />
                </div>
              </ShadTooltip>
            )}
          </div>
        </div>
        {left && LANGFLOW_SUPPORTED_TYPES.has(type ?? "") && !optionalHandle ? (
          <></>
        ) : (
          <Button className="h-7 truncate bg-muted p-0 text-sm font-normal text-black hover:bg-muted">
            <div className="flex">
              <ShadTooltip
                styleClasses={"tooltip-fixed-width custom-scroll nowheel"}
                delayDuration={1000}
                content={refHtml.current}
                side={left ? "left" : "right"}
              >
                <Handle
                  data-test-id={`handle-${title.toLowerCase()}-${
                    left ? "left" : "right"
                  }`}
                  type={left ? "target" : "source"}
                  position={left ? Position.Left : Position.Right}
                  key={
                    proxy
                      ? scapedJSONStringfy({ ...id, proxy })
                      : scapedJSONStringfy(id)
                  }
                  id={
                    proxy
                      ? scapedJSONStringfy({ ...id, proxy })
                      : scapedJSONStringfy(id)
                  }
                  isValidConnection={(connection) =>
                    isValidConnection(connection, nodes, edges)
                  }
                  className={classNames(
                    left ? "-ml-0.5 " : "-mr-0.5 ",
                    "h-3 w-3 rounded-full border-2 bg-background"
                  )}
                  style={{
                    borderColor: color ?? nodeColors.unknown,
                  }}
                  onClick={() => {
                    setFilterEdge(groupedEdge.current);
                  }}
                ></Handle>
              </ShadTooltip>
            </div>
          </Button>
        )}

        {left === true &&
        type === "str" &&
        !data.node?.template[name].options ? (
          <div className="w-full">
            {data.node?.template[name].list ? (
              <div
                className={
                  // Commenting this out until we have a better
                  // way to display
                  // (data.node?.template[name].refresh ? "w-5/6 " : "") +
                  "flex-grow"
                }
              >
                <InputListComponent
                  componentName={name}
                  disabled={disabled}
                  value={
                    !data.node.template[name].value ||
                    data.node.template[name].value === ""
                      ? [""]
                      : data.node.template[name].value
                  }
                  onChange={handleOnNewValue}
                />
                {/* {data.node?.template[name].refresh_button && (
                  <div className="w-1/6">
                    <RefreshButton
                      isLoading={isLoading}
                      disabled={disabled}
                      name={name}
                      data={data}
                      className="extra-side-bar-buttons ml-2 mt-1"
                      handleUpdateValues={handleRefreshButtonPress}
                      id={"refresh-button-" + name}
                    />
                  </div>
                )} */}
              </div>
            ) : data.node?.template[name].multiline ? (
              <div className="mt-2 flex w-full flex-col ">
                <div className="flex-grow">
                  <TextAreaComponent
                    disabled={disabled}
                    value={data.node.template[name].value ?? ""}
                    onChange={handleOnNewValue}
                    id={"textarea-" + data.node.template[name].name}
                    data-testid={"textarea-" + data.node.template[name].name}
                  />
                </div>
                {data.node?.template[name].refresh_button && (
                  <div className="flex-grow">
                    <RefreshButton
                      isLoading={isLoading}
                      disabled={disabled}
                      name={name}
                      data={data}
                      button_text={
                        data.node?.template[name].refresh_button_text ??
                        "Refresh"
                      }
                      className="extra-side-bar-buttons mt-1"
                      handleUpdateValues={handleRefreshButtonPress}
                      id={"refresh-button-" + name}
                    />
                  </div>
                )}
              </div>
            ) : (
              <div className="mt-2 flex w-full items-center">
                <div
                  className={
                    "flex-grow " +
                    (data.node?.template[name].refresh_button ? "w-5/6" : "")
                  }
                >
                  <InputGlobalComponent
                    disabled={disabled}
                    onChange={handleOnNewValue}
                    setDb={(value) => {
                      setNode(data.id, (oldNode) => {
                        let newNode = cloneDeep(oldNode);
                        newNode.data = {
                          ...newNode.data,
                        };
                        newNode.data.node.template[name].load_from_db = value;
                        return newNode;
                      });
                    }}
                    name={name}
                    data={data}
                  />
                </div>
                {data.node?.template[name].refresh_button && (
                  <div className="w-1/6">
                    <RefreshButton
                      isLoading={isLoading}
                      disabled={disabled}
                      name={name}
                      data={data}
                      button_text={
                        data.node?.template[name].refresh_button_text ??
                        "Refresh"
                      }
                      className="extra-side-bar-buttons ml-2 mt-1"
                      handleUpdateValues={handleRefreshButtonPress}
                      id={"refresh-button-" + name}
                    />
                  </div>
                )}
              </div>
            )}
          </div>
        ) : left === true && type === "bool" ? (
          <div className="mt-2 w-full">
            <ToggleShadComponent
              id={"toggle-" + name}
              disabled={disabled}
              enabled={data.node?.template[name].value ?? false}
              setEnabled={handleOnNewValue}
              size="large"
              editNode={false}
            />
          </div>
        ) : left === true && type === "float" ? (
          <div className="mt-2 w-full">
            <FloatComponent
              disabled={disabled}
              value={data.node?.template[name].value ?? ""}
              rangeSpec={data.node?.template[name]?.rangeSpec}
              onChange={handleOnNewValue}
            />
          </div>
        ) : left === true &&
          type === "str" &&
          (data.node?.template[name].options ||
            data.node?.template[name]?.real_time_refresh) ? (
          // TODO: Improve CSS
          <div className="mt-2 flex w-full items-center">
            <div className="w-5/6 flex-grow">
              <Dropdown
                disabled={disabled}
                isLoading={isLoading}
                options={data.node.template[name].options}
                onSelect={handleOnNewValue}
                value={data.node.template[name].value}
                id={"dropdown-" + name}
              />
            </div>
            {data.node?.template[name].refresh_button && (
              <div className="w-1/6">
                <RefreshButton
                  isLoading={isLoading}
                  disabled={disabled}
                  name={name}
                  data={data}
                  button_text={data.node?.template[name].refresh_button_text}
                  className="extra-side-bar-buttons ml-2 mt-1"
                  handleUpdateValues={handleRefreshButtonPress}
                  id={"refresh-button-" + name}
                />
              </div>
            )}
          </div>
        ) : left === true && type === "code" ? (
          <div className="mt-2 w-full">
            <CodeAreaComponent
              readonly={
                data.node?.flow && data.node.template[name].dynamic
                  ? true
                  : false
              }
              dynamic={data.node?.template[name].dynamic ?? false}
              setNodeClass={handleNodeClass}
              nodeClass={data.node}
              disabled={disabled}
              value={data.node?.template[name].value ?? ""}
              onChange={handleOnNewValue}
              id={"code-input-" + name}
            />
          </div>
        ) : left === true && type === "file" ? (
          <div className="mt-2 w-full">
            <InputFileComponent
              disabled={disabled}
              value={data.node?.template[name].value ?? ""}
              onChange={handleOnNewValue}
              fileTypes={data.node?.template[name].fileTypes}
              onFileChange={(filePath: string) => {
                data.node!.template[name].file_path = filePath;
              }}
            ></InputFileComponent>
          </div>
        ) : left === true && type === "int" ? (
          <div className="mt-2 w-full">
            <IntComponent
              rangeSpec={data.node?.template[name].rangeSpec}
              disabled={disabled}
              value={data.node?.template[name].value ?? ""}
              onChange={handleOnNewValue}
              id={"int-input-" + name}
            />
          </div>
        ) : left === true && type === "prompt" ? (
          <div className="mt-2 w-full">
            <PromptAreaComponent
              readonly={data.node?.flow ? true : false}
              field_name={name}
              setNodeClass={handleNodeClass}
              nodeClass={data.node}
              disabled={disabled}
              value={data.node?.template[name].value ?? ""}
              onChange={handleOnNewValue}
              id={"prompt-input-" + name}
              data-testid={"prompt-input-" + name}
            />
          </div>
        ) : left === true && type === "NestedDict" ? (
          <div className="mt-2 w-full">
            <DictComponent
              disabled={disabled}
              editNode={false}
              value={
                !data.node!.template[name].value ||
                data.node!.template[name].value?.toString() === "{}"
                  ? {
                      yourkey: "value",
                    }
                  : data.node!.template[name].value
              }
              onChange={handleOnNewValue}
              id="div-dict-input"
            />
          </div>
        ) : left === true && type === "dict" ? (
          <div className="mt-2 w-full">
            <KeypairListComponent
              disabled={disabled}
              editNode={false}
              value={
                data.node!.template[name].value?.length === 0 ||
                !data.node!.template[name].value
                  ? [{ "": "" }]
                  : convertObjToArray(data.node!.template[name].value)
              }
              duplicateKey={errorDuplicateKey}
              onChange={(newValue) => {
                const valueToNumbers = convertValuesToNumbers(newValue);
                setErrorDuplicateKey(hasDuplicateKeys(valueToNumbers));
                // if data.node?.template[name].list is true, then the value is an array of objects
                // else we need to get the first object of the array

                if (data.node?.template[name].list) {
                  handleOnNewValue(valueToNumbers);
                } else handleOnNewValue(valueToNumbers[0]);
              }}
              isList={data.node?.template[name].list ?? false}
            />
          </div>
        ) : (
          <></>
        )}
      </>
    </div>
  );
}
