import { cloneDeep } from "lodash";
import React, { ReactNode, useEffect, useRef, useState } from "react";
import { Handle, Position, useUpdateNodeInternals } from "reactflow";
import ShadTooltip from "../../../../components/ShadTooltipComponent";
import CodeAreaComponent from "../../../../components/codeAreaComponent";
import DictComponent from "../../../../components/dictComponent";
import Dropdown from "../../../../components/dropdownComponent";
import FloatComponent from "../../../../components/floatComponent";
import IconComponent from "../../../../components/genericIconComponent";
import InputComponent from "../../../../components/inputComponent";
import InputFileComponent from "../../../../components/inputFileComponent";
import InputListComponent from "../../../../components/inputListComponent";
import IntComponent from "../../../../components/intComponent";
import KeypairListComponent from "../../../../components/keypairListComponent";
import PromptAreaComponent from "../../../../components/promptComponent";
import TextAreaComponent from "../../../../components/textAreaComponent";
import ToggleShadComponent from "../../../../components/toggleShadComponent";
import { Button } from "../../../../components/ui/button";
import {
  LANGFLOW_SUPPORTED_TYPES,
  TOOLTIP_EMPTY,
} from "../../../../constants/constants";
import { postCustomComponentUpdate } from "../../../../controllers/API";
import useAlertStore from "../../../../stores/alertStore";
import useFlowStore from "../../../../stores/flowStore";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { useTypesStore } from "../../../../stores/typesStore";
import { APIClassType } from "../../../../types/api";
import { ParameterComponentType } from "../../../../types/components";
import { NodeDataType } from "../../../../types/flow";
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

  const handleUpdateValues = async (name: string, data: NodeDataType) => {
    const code = data.node?.template["code"]?.value;
    if (!code) {
      console.error("Code not found in the template");
      return;
    }

    try {
      const res = await postCustomComponentUpdate(code, name);
      if (res.status === 200 && data.node?.template) {
        data.node!.template[name] = res.data.template[name];
      }
    } catch (err) {
      setErrorData(err as { title: string; list?: Array<string> });
    }
  };

  const handleOnNewValue = (
    newValue: string | string[] | boolean | Object[]
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
          <div key={index}>
            {index === 0 && (
              <span>
                {left
                  ? "Avaliable input components:"
                  : "Avaliable output components:"}
              </span>
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
              <span className="ps-2 text-xs text-foreground">
                {nodeNames[item.family] ?? "Other"}{" "}
                {item?.display_name && item?.display_name?.length > 0 ? (
                  <span className="text-xs">
                    {" "}
                    {item.display_name === "" ? "" : " - "}
                    {item.display_name.split(", ").length > 2
                      ? item.display_name.split(", ").map((el, index) => (
                          <React.Fragment key={el + index}>
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
                  <span className="text-xs">
                    {" "}
                    {item.type === "" ? "" : " - "}
                    {item.type.split(", ").length > 2
                      ? item.type.split(", ").map((el, index) => (
                          <React.Fragment key={el + index}>
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
      refHtml.current = <span>{TOOLTIP_EMPTY}</span>;
    }
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
            delayDuration={0}
            content={refHtml.current}
            side={left ? "left" : "right"}
          >
            <Handle
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
                borderColor: color,
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
      className="relative mt-1 flex w-full flex-wrap items-center justify-between bg-muted px-5 py-2"
    >
      <>
        <div
          className={
            "w-full truncate text-sm" +
            (left ? "" : " text-end") +
            (info !== "" ? " flex items-center" : "")
          }
        >
          {proxy ? (
            <ShadTooltip content={<span>{proxy.id}</span>}>
              <span>{title}</span>
            </ShadTooltip>
          ) : (
            title
          )}
          <span className="text-status-red">{required ? " *" : ""}</span>
          <div className="">
            {info !== "" && (
              <ShadTooltip content={infoHtml.current}>
                {/* put div to avoid bug that does not display tooltip */}
                <div>
                  <IconComponent
                    name="Info"
                    className="relative bottom-0.5 ml-2 h-3 w-4"
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
                delayDuration={0}
                content={refHtml.current}
                side={left ? "left" : "right"}
              >
                <Handle
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
                    borderColor: color,
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
          <div className="mt-2 w-full">
            {data.node?.template[name].list ? (
              <InputListComponent
                disabled={disabled}
                value={
                  !data.node.template[name].value ||
                  data.node.template[name].value === ""
                    ? [""]
                    : data.node.template[name].value
                }
                onChange={handleOnNewValue}
              />
            ) : data.node?.template[name].multiline ? (
              <TextAreaComponent
                disabled={disabled}
                value={data.node.template[name].value ?? ""}
                onChange={handleOnNewValue}
                id={"textarea-" + data.node.template[name].name}
                data-testid={"textarea-" + data.node.template[name].name}
              />
            ) : (
              <InputComponent
                id={"input-" + index}
                disabled={disabled}
                password={data.node?.template[name].password ?? false}
                value={data.node?.template[name].value ?? ""}
                onChange={handleOnNewValue}
              />
            )}
          </div>
        ) : left === true && type === "bool" ? (
          <div className="mt-2 w-full">
            <ToggleShadComponent
              id={"toggle-" + index}
              disabled={disabled}
              enabled={data.node?.template[name].value ?? false}
              setEnabled={handleOnNewValue}
              size="large"
            />
          </div>
        ) : left === true && type === "float" ? (
          <div className="mt-2 w-full">
            <FloatComponent
              disabled={disabled}
              value={data.node?.template[name].value ?? ""}
              rangeSpec={data.node?.template[name].rangeSpec}
              onChange={handleOnNewValue}
            />
          </div>
        ) : left === true &&
          type === "str" &&
          data.node?.template[name].options ? (
          // TODO: Improve CSS
          <div className="mt-2 flex w-full items-center">
            <div className="w-5/6 flex-grow">
              <Dropdown
                options={data.node.template[name].options}
                onSelect={handleOnNewValue}
                value={data.node.template[name].value ?? "Choose an option"}
                id={"dropdown-" + index}
              />
            </div>
            {data.node?.template[name].refresh && (
              <button
                className="extra-side-bar-buttons ml-2 mt-1 w-1/6"
                onClick={() => {
                  handleUpdateValues(name, data);
                }}
              >
                <IconComponent name="RefreshCcw" />
              </button>
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
              id={"code-input-" + index}
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
              disabled={disabled}
              value={data.node?.template[name].value ?? ""}
              onChange={handleOnNewValue}
              id={"int-input-" + index}
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
              id={"prompt-input-" + index}
              data-testid={"prompt-input-" + index}
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
                handleOnNewValue(valueToNumbers);
              }}
            />
          </div>
        ) : (
          <></>
        )}
      </>
    </div>
  );
}
