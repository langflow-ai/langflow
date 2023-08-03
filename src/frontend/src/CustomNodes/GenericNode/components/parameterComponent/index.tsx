import { cloneDeep } from "lodash";
import React, { useContext, useEffect, useRef, useState } from "react";
import { Handle, Position, useUpdateNodeInternals } from "reactflow";
import ShadTooltip from "../../../../components/ShadTooltipComponent";
import CodeAreaComponent from "../../../../components/codeAreaComponent";
import Dropdown from "../../../../components/dropdownComponent";
import FloatComponent from "../../../../components/floatComponent";
import IconComponent from "../../../../components/genericIconComponent";
import InputComponent from "../../../../components/inputComponent";
import InputFileComponent from "../../../../components/inputFileComponent";
import InputListComponent from "../../../../components/inputListComponent";
import IntComponent from "../../../../components/intComponent";
import PromptAreaComponent from "../../../../components/promptComponent";
import TextAreaComponent from "../../../../components/textAreaComponent";
import ToggleShadComponent from "../../../../components/toggleShadComponent";
import { TOOLTIP_EMPTY } from "../../../../constants/constants";
import { TabsContext } from "../../../../contexts/tabsContext";
import { typesContext } from "../../../../contexts/typesContext";
import { ParameterComponentType } from "../../../../types/components";
import { isValidConnection } from "../../../../utils/reactflowUtils";
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
  setData,
  tooltipTitle,
  title,
  color,
  type,
  name = "",
  required = false,
  optionalHandle = null,
  info = "",
}: ParameterComponentType) {
  const ref = useRef(null);
  const refHtml = useRef(null);
  const infoHtml = useRef(null);
  const groupedEdge = useRef(null);
  const updateNodeInternals = useUpdateNodeInternals();
  const [position, setPosition] = useState(0);
  const { setTabsState, tabId, save, flows } = useContext(TabsContext);

  const flow = flows.find((f) => f.id === tabId).data?.nodes ?? null;

  // Update component position
  useEffect(() => {
    if (ref.current && ref.current.offsetTop && ref.current.clientHeight) {
      setPosition(ref.current.offsetTop + ref.current.clientHeight / 2);
      updateNodeInternals(data.id);
    }
  }, [data.id, ref, ref.current, ref.current?.offsetTop, updateNodeInternals]);

  useEffect(() => {
    updateNodeInternals(data.id);
  }, [data.id, position, updateNodeInternals]);

  const { reactFlowInstance } = useContext(typesContext);
  let disabled =
    reactFlowInstance?.getEdges().some((e) => e.targetHandle === id) ?? false;
  let disabledLeft =
    reactFlowInstance?.getEdges().some((e) => e.sourceHandle === id) ?? false;

  const { data: myData, setFilterEdge } = useContext(typesContext);

  const handleOnNewValue = (newValue: any) => {
    let newData = cloneDeep(data);
    newData.node.template[name].value = newValue;
    setData(newData);
    // Set state to pending
    setTabsState((prev) => {
      return {
        ...prev,
        [tabId]: {
          ...prev[tabId],
          isPending: true,
          formKeysData: prev[tabId].formKeysData,
        },
      };
    });
    renderTooltips();
  };

  useEffect(() => {
    if (name === "openai_api_base") console.log(info);
    infoHtml.current = (
      <div className="h-full w-full break-words">
        {info.split("\n").map((line, i) => (
          <p key={i} className="block">
            {line}
          </p>
        ))}
      </div>
    );
  }, [info]);

  function renderTooltips() {
    let groupedObj = groupByFamily(myData, tooltipTitle, left, flow);

    groupedEdge.current = groupedObj;

    if (groupedObj && groupedObj.length > 0) {
      refHtml.current = groupedObj.map((item, i) => {
        const Icon: any =
          nodeIconsLucide[item.family] ?? nodeIconsLucide["unknown"];

        return (
          <span
            key={i}
            className={classNames(
              i > 0 ? "mt-2 flex items-center" : "flex items-center"
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
              {nodeNames[item.family] ?? "Other"}
              <span className="text-xs">
                {" "}
                {item.type === "" ? "" : " - "}
                {item.type.split(", ").length > 2
                  ? item.type.split(", ").map((el, i) => (
                      <React.Fragment key={el + i}>
                        <span>
                          {i === item.type.split(", ").length - 1
                            ? el
                            : (el += `, `)}
                        </span>
                      </React.Fragment>
                    ))
                  : item.type}
              </span>
            </span>
          </span>
        );
      });
    } else {
      refHtml.current = <span>{TOOLTIP_EMPTY}</span>;
    }
  }

  useEffect(() => {
    renderTooltips();
  }, [tooltipTitle, flow]);

  return (
    <div
      ref={ref}
      className="mt-1 flex w-full flex-wrap items-center justify-between bg-muted px-5 py-2"
    >
      <>
        <div
          className={
            "w-full truncate text-sm" +
            (left ? "" : " text-end") +
            (info !== "" ? " flex items-center" : "")
          }
        >
          <div className="truncate bg-muted text-sm font-normal hover:bg-muted">
            {title}
          </div>

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
        {left &&
        (type === "str" ||
          type === "bool" ||
          type === "float" ||
          type === "code" ||
          type === "prompt" ||
          type === "file" ||
          type === "int") &&
        !optionalHandle ? (
          <></>
        ) : (
          <ShadTooltip
            styleClasses={"tooltip-fixed-width custom-scroll nowheel"}
            delayDuration={0}
            content={refHtml.current}
            side={left ? "left" : "right"}
          >
            <Handle
              type={left ? "target" : "source"}
              position={left ? Position.Left : Position.Right}
              id={id}
              isValidConnection={(connection) =>
                isValidConnection(connection, reactFlowInstance)
              }
              className={classNames(
                left ? "-ml-1.5 " : "-mr-1.5 ",
                "group flex h-5 w-5 items-center justify-center rounded-full border-border"
              )}
              style={{
                backgroundColor: color,
                top: position,
              }}
              onMouseUp={() => {
                setFilterEdge(groupedEdge.current);
              }}
            >
              <IconComponent
                name="Filter"
                className={
                  "pointer-events-none absolute -mb-0.5 h-3 w-3 fill-background stroke-none transition-all group-hover:h-4 group-hover:w-4 " +
                  (!disabled && !disabledLeft ? "scale-100" : "scale-0")
                }
              />
              <div
                className={
                  "pointer-events-none absolute h-3 w-3 rounded-full bg-background transition-all " +
                  (!disabled && !disabledLeft ? "scale-0" : "scale-100")
                }
              ></div>
            </Handle>
          </ShadTooltip>
        )}

        {left === true &&
        type === "str" &&
        !data.node.template[name].options ? (
          <div className="mt-2 w-full">
            {data.node.template[name].list ? (
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
            ) : data.node.template[name].multiline ? (
              <TextAreaComponent
                disabled={disabled}
                value={data.node.template[name].value ?? ""}
                onChange={handleOnNewValue}
              />
            ) : (
              <InputComponent
                disabled={disabled}
                password={data.node.template[name].password ?? false}
                value={data.node.template[name].value ?? ""}
                onChange={handleOnNewValue}
              />
            )}
          </div>
        ) : left === true && type === "bool" ? (
          <div className="mt-2 w-full">
            <ToggleShadComponent
              disabled={disabled}
              enabled={data.node.template[name].value ?? false}
              setEnabled={(t) => {
                handleOnNewValue(t);
              }}
              size="large"
            />
          </div>
        ) : left === true && type === "float" ? (
          <div className="mt-2 w-full">
            <FloatComponent
              disabled={disabled}
              value={data.node.template[name].value ?? ""}
              onChange={handleOnNewValue}
            />
          </div>
        ) : left === true &&
          type === "str" &&
          data.node.template[name].options ? (
          <div className="mt-2 w-full">
            <Dropdown
              options={data.node.template[name].options}
              onSelect={handleOnNewValue}
              value={data.node.template[name].value ?? "Choose an option"}
            ></Dropdown>
          </div>
        ) : left === true && type === "code" ? (
          <div className="mt-2 w-full">
            <CodeAreaComponent
              dynamic={data.node.template[name].dynamic ?? false}
              setNodeClass={(nodeClass) => {
                data.node = nodeClass;
              }}
              nodeClass={data.node}
              disabled={disabled}
              value={data.node.template[name].value ?? ""}
              onChange={handleOnNewValue}
            />
          </div>
        ) : left === true && type === "file" ? (
          <div className="mt-2 w-full">
            <InputFileComponent
              disabled={disabled}
              value={data.node.template[name].value ?? ""}
              onChange={handleOnNewValue}
              fileTypes={data.node.template[name].fileTypes}
              suffixes={data.node.template[name].suffixes}
              onFileChange={(t: string) => {
                data.node.template[name].file_path = t;
                save();
              }}
            ></InputFileComponent>
          </div>
        ) : left === true && type === "int" ? (
          <div className="mt-2 w-full">
            <IntComponent
              disabled={disabled}
              value={data.node.template[name].value ?? ""}
              onChange={handleOnNewValue}
            />
          </div>
        ) : left === true && type === "prompt" ? (
          <div className="mt-2 w-full">
            <PromptAreaComponent
              field_name={name}
              setNodeClass={(nodeClass) => {
                data.node = nodeClass;
              }}
              nodeClass={data.node}
              disabled={disabled}
              value={data.node.template[name].value ?? ""}
              onChange={handleOnNewValue}
            />
          </div>
        ) : (
          <></>
        )}
      </>
    </div>
  );
}
