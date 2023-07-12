import { Info } from "lucide-react";
import React, { useContext, useEffect, useRef, useState } from "react";
import { Handle, Position, useUpdateNodeInternals } from "reactflow";
import ShadTooltip from "../../../../components/ShadTooltipComponent";
import CodeAreaComponent from "../../../../components/codeAreaComponent";
import Dropdown from "../../../../components/dropdownComponent";
import FloatComponent from "../../../../components/floatComponent";
import InputComponent from "../../../../components/inputComponent";
import InputFileComponent from "../../../../components/inputFileComponent";
import InputListComponent from "../../../../components/inputListComponent";
import IntComponent from "../../../../components/intComponent";
import PromptAreaComponent from "../../../../components/promptComponent";
import TextAreaComponent from "../../../../components/textAreaComponent";
import ToggleShadComponent from "../../../../components/toggleShadComponent";
import { MAX_LENGTH_TO_SCROLL_TOOLTIP } from "../../../../constants";
import { PopUpContext } from "../../../../contexts/popUpContext";
import { TabsContext } from "../../../../contexts/tabsContext";
import { typesContext } from "../../../../contexts/typesContext";
import { ParameterComponentType } from "../../../../types/components";
import { cleanEdges } from "../../../../util/reactflowUtils";
import {
  classNames,
  getRandomKeyByssmm,
  groupByFamily,
  isValidConnection,
  nodeColors,
  nodeIconsLucide,
  nodeNames,
} from "../../../../utils";

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
}: ParameterComponentType) {
  const ref = useRef(null);
  const refHtml = useRef(null);
  const refNumberComponents = useRef(0);
  const infoHtml = useRef(null);
  const updateNodeInternals = useUpdateNodeInternals();
  const [position, setPosition] = useState(0);
  const { closePopUp } = useContext(PopUpContext);
  const { setTabsState, tabId, save } = useContext(TabsContext);

  useEffect(() => {
    if (ref.current && ref.current.offsetTop && ref.current.clientHeight) {
      setPosition(ref.current.offsetTop + ref.current.clientHeight / 2);
      updateNodeInternals(data.id);
    }
  }, [data.id, ref, ref.current, ref.current?.offsetTop, updateNodeInternals]);

  useEffect(() => {
    updateNodeInternals(data.id);
  }, [data.id, position, updateNodeInternals]);

  useEffect(() => {}, [closePopUp, data.node.template]);

  const { reactFlowInstance } = useContext(typesContext);
  let disabled =
    reactFlowInstance?.getEdges().some((e) => e.targetHandle === id) ?? false;
  const [myData, setMyData] = useState(useContext(typesContext).data);

  const handleOnNewValue = (newValue: any) => {
    data.node.template[name].value = newValue;
    // Set state to pending
    setTabsState((prev) => {
      return {
        ...prev,
        [tabId]: {
          ...prev[tabId],
          isPending: true,
        },
      };
    });
  };

  useEffect(() => {
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

  useEffect(() => {
    const groupedObj = groupByFamily(myData, tooltipTitle, left, data.type);

    refNumberComponents.current = groupedObj[0]?.type?.length;

    refHtml.current = groupedObj.map((item, i) => {
      const Icon: any = nodeIconsLucide[item.family];

      return (
        <span
          key={getRandomKeyByssmm() + item.family + i}
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
            {nodeNames[item.family] ?? ""}{" "}
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
  }, [tooltipTitle]);

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
          {title}
          <span className="text-status-red">{required ? " *" : ""}</span>
          <div className="">
            {info !== "" && (
              <ShadTooltip content={infoHtml.current}>
                <Info className="relative bottom-0.5 ml-2 h-3 w-3" />
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
            styleClasses={
              refNumberComponents.current > MAX_LENGTH_TO_SCROLL_TOOLTIP
                ? "tooltip-fixed-width custom-scroll overflow-y-scroll nowheel"
                : "tooltip-fixed-width"
            }
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
                left ? "-ml-0.5 " : "-mr-0.5 ",
                "h-3 w-3 rounded-full border-2 bg-background"
              )}
              style={{
                borderColor: color,
                top: position,
              }}
            ></Handle>
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
                disableCopyPaste={true}
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
              enabled={data.node.template[name].value}
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
              disableCopyPaste={true}
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
              disableCopyPaste={true}
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
                if (reactFlowInstance) {
                  cleanEdges({
                    flow: {
                      edges: reactFlowInstance.getEdges(),
                      nodes: reactFlowInstance.getNodes(),
                    },
                    updateEdge: (edge) => reactFlowInstance.setEdges(edge),
                  });
                }
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
