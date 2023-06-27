import { Handle, Position, useUpdateNodeInternals } from "reactflow";
import {
  classNames,
  getRandomKeyByssmm,
  groupByFamily,
  isValidConnection,
  nodeIconsLucide,
} from "../../../../utils";
import { useContext, useEffect, useRef, useState } from "react";
import InputComponent from "../../../../components/inputComponent";
import InputListComponent from "../../../../components/inputListComponent";
import TextAreaComponent from "../../../../components/textAreaComponent";
import { typesContext } from "../../../../contexts/typesContext";
import { ParameterComponentType } from "../../../../types/components";
import FloatComponent from "../../../../components/floatComponent";
import Dropdown from "../../../../components/dropdownComponent";
import CodeAreaComponent from "../../../../components/codeAreaComponent";
import InputFileComponent from "../../../../components/inputFileComponent";
import { TabsContext } from "../../../../contexts/tabsContext";
import IntComponent from "../../../../components/intComponent";
import PromptAreaComponent from "../../../../components/promptComponent";
import { nodeNames } from "../../../../utils";
import React from "react";
import { nodeColors } from "../../../../utils";
import ShadTooltip from "../../../../components/ShadTooltipComponent";
import { PopUpContext } from "../../../../contexts/popUpContext";
import ToggleShadComponent from "../../../../components/toggleShadComponent";
import { Info } from "lucide-react";

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
  info = "",
}: ParameterComponentType) {
  const ref = useRef(null);
  const refHtml = useRef(null);
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

  const [enabled, setEnabled] = useState(
    data.node.template[name]?.value ?? false
  );

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
    const groupedObj = groupByFamily(myData, tooltipTitle);

    refHtml.current = groupedObj.map((item, i) => (
      <span
        key={getRandomKeyByssmm()}
        className={classNames(
          i > 0 ? "items-center flex mt-3" : "items-center flex"
        )}
      >
        <div
          className="h-6 w-6"
          style={{
            color: nodeColors[item.family],
          }}
        >
          {React.createElement(nodeIconsLucide[item.family])}
        </div>
        <span className="ps-2 text-gray-950">
          {nodeNames[item.family] ?? ""}{" "}
          <span className={classNames(left ? "hidden" : "")}>
            {" "}
            -&nbsp;
            {item.type.split(", ").length > 2
              ? item.type.split(", ").map((el, i) => (
                  <React.Fragment key={el + i}>
                    <span>
                      {i === item.type.split(", ").length - 1
                        ? el
                        : (el += `, `)}
                    </span>
                    {i % 2 === 0 && i > 0 && <br />}
                  </React.Fragment>
                ))
              : item.type}
          </span>
        </span>
      </span>
    ));
  }, [tooltipTitle]);

  return (
    <div
      ref={ref}
      className="w-full flex flex-wrap justify-between items-center bg-muted dark:bg-gray-800 dark:text-white mt-1 px-5 py-2"
    >
      <>
        <div
          className={
            "text-sm truncate w-full" +
            (left ? "" : " text-end") +
            (info !== "" ? " flex items-center" : "")
          }
        >
          {title}
          <span className="text-red-600">{required ? " *" : ""}</span>
          <div className="">
            {info !== "" && (
              <ShadTooltip content={infoHtml.current}>
                <Info className="ml-2 relative bottom-0.5 w-3 h-3" />
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
          type === "int") ? (
          <></>
        ) : (
          <ShadTooltip
            delayDuration={0}
            content={refHtml.current}
            side={left ? "left" : "right"}
            open={refHtml?.current?.length > 0}
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
                "w-3 h-3 rounded-full border-2 bg-white dark:bg-gray-800"
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
          <div className="mt-2">
            <ToggleShadComponent
              disabled={disabled}
              enabled={enabled}
              setEnabled={(t) => {
                handleOnNewValue(t);
                setEnabled(t);
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
          <div className="w-full">
            <Dropdown
              options={data.node.template[name].options}
              onSelect={handleOnNewValue}
              value={data.node.template[name].value ?? "Choose an option"}
            ></Dropdown>
          </div>
        ) : left === true && type === "code" ? (
          <CodeAreaComponent
            disabled={disabled}
            value={data.node.template[name].value ?? ""}
            onChange={handleOnNewValue}
          />
        ) : left === true && type === "file" ? (
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
          <PromptAreaComponent
            disabled={disabled}
            value={data.node.template[name].value ?? ""}
            onChange={handleOnNewValue}
          />
        ) : (
          <></>
        )}
      </>
    </div>
  );
}
