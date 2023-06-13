import { Tooltip } from "@mui/material";
import { useRef, useState, useEffect, useContext } from "react";
import { useUpdateNodeInternals, Handle, Position } from "reactflow";
import CodeAreaComponent from "../../../../../../components/codeAreaComponent";
import Dropdown from "../../../../../../components/dropdownComponent";
import FloatComponent from "../../../../../../components/floatComponent";
import InputComponent from "../../../../../../components/inputComponent";
import InputFileComponent from "../../../../../../components/inputFileComponent";
import InputListComponent from "../../../../../../components/inputListComponent";
import IntComponent from "../../../../../../components/intComponent";
import PromptAreaComponent from "../../../../../../components/promptComponent";
import TextAreaComponent from "../../../../../../components/textAreaComponent";
import ToggleComponent from "../../../../../../components/toggleComponent";
import { TabsContext } from "../../../../../../contexts/tabsContext";
import { typesContext } from "../../../../../../contexts/typesContext";
import {
  HandleComponentType,
  ParameterComponentType,
} from "../../../../../../types/components";
import { isValidConnection, classNames, groupByFamily, nodeColors, nodeIcons, nodeNames } from "../../../../../../utils";
import React from "react";
import ShadTooltip from "../../../../../../components/ShadTooltipComponent";

export default function HandleComponent({
  left,
  id,
  data,
  tooltipTitle,
  title,
  color,
  type,
  handleDisabled,
  name = "",
  required = false,
  fill = false,
  position,
}: HandleComponentType) {
  const [enabled, setEnabled] = useState(
    data.node.template[name]?.value ?? false
  );
  const { reactFlowInstance } = useContext(typesContext);
  let disabled =
    reactFlowInstance?.getEdges().some((e) => e.targetHandle === id) ?? false;
  const { save } = useContext(TabsContext);
  const [myData, setMyData] = useState(useContext(typesContext).data);
  const refHtml = useRef(null);

  useEffect(() => {
    const groupedObj = groupByFamily(myData, tooltipTitle);

    refHtml.current = groupedObj.map((item, i) => (
      <span
        key={i}
        className={classNames(
          i > 0 ? "items-center flex mt-3" : "items-center flex"
        )}
      >
        <div
          className="h-5 w-5"
          style={{
            color: nodeColors[item.family],
          }}
        >
          {React.createElement(nodeIcons[item.family])}
        </div>
        <span className="ps-2 text-gray-950">
          {nodeNames[item.family] ?? ""}{" "}
          <span className={classNames(left ? "hidden" : "")}>
            {" "}
            -&nbsp;
            {item.type.split(", ").length > 2
              ? item.type.split(", ").map((el, i) => (
                  <>
                    <span key={i}>
                      {i == item.type.split(", ").length - 1
                        ? el
                        : (el += `, `)}
                    </span>
                    {i % 2 == 0 && i > 0 && <br></br>}
                  </>
                ))
              : item.type}
          </span>
        </span>
      </span>
    ));
  }, [tooltipTitle]);


  return (
    <>
      <div
        className={
          "truncate text-sm " + (handleDisabled ? "text-gray-500" : "")
        }
      >
        {title}
        <span className="text-red-600">{required ? " *" : ""}</span>
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
      >
          <Handle
            type={left ? "target" : "source"}
            position={left ? Position.Left : Position.Right}
            id={id}
            isValidConnection={(connection) =>
              handleDisabled
                ? false
                : isValidConnection(connection, reactFlowInstance)
            }
            className={classNames(
              left ? "-ml-0.5 " : "-mr-0.5 ",
              "h-3 w-3 rounded-full border-2 dark:bg-gray-800",
              handleDisabled && "pointer-events-none"
            )}
            style={{
              borderColor: handleDisabled ? "lightGray" : color,
              top: position,
              backgroundColor: fill
                ? handleDisabled
                  ? "lightGray"
                  : color
                : "white",
            }}
          ></Handle>
      </ShadTooltip>
      )}

      {data &&
        (left === true &&
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
                onChange={(t: string[]) => {
                  data.node.template[name].value = t;
                  save();
                }}
              />
            ) : data.node.template[name].multiline ? (
              <TextAreaComponent
                disabled={disabled}
                value={data.node.template[name].value ?? ""}
                onChange={(t: string) => {
                  data.node.template[name].value = t;
                  save();
                }}
              />
            ) : (
              <InputComponent
                disabled={disabled}
                password={data.node.template[name].password ?? false}
                value={data.node.template[name].value ?? ""}
                onChange={(t) => {
                  data.node.template[name].value = t;
                  save();
                }}
              />
            )}
          </div>
        ) : left === true && type === "bool" ? (
          <div className="mt-2">
            <ToggleComponent
              disabled={disabled}
              enabled={enabled}
              setEnabled={(t) => {
                data.node.template[name].value = t;
                setEnabled(t);
                save();
              }}
            />
          </div>
        ) : left === true && type === "float" ? (
          <FloatComponent
            disabled={disabled}
            value={data.node.template[name].value ?? ""}
            onChange={(t) => {
              data.node.template[name].value = t;
              save();
            }}
          />
        ) : left === true &&
          type === "str" &&
          data.node.template[name].options ? (
          <Dropdown
            options={data.node.template[name].options}
            onSelect={(newValue) => (data.node.template[name].value = newValue)}
            value={data.node.template[name].value ?? "Choose an option"}
          ></Dropdown>
        ) : left === true && type === "code" ? (
          <CodeAreaComponent
            disabled={disabled}
            value={data.node.template[name].value ?? ""}
            onChange={(t: string) => {
              data.node.template[name].value = t;
              save();
            }}
          />
        ) : left === true && type === "file" ? (
          <InputFileComponent
            disabled={disabled}
            value={data.node.template[name].value ?? ""}
            onChange={(t: string) => {
              data.node.template[name].value = t;
            }}
            fileTypes={data.node.template[name].fileTypes}
            suffixes={data.node.template[name].suffixes}
            onFileChange={(t: string) => {
              data.node.template[name].content = t;
              save();
            }}
          ></InputFileComponent>
        ) : left === true && type === "int" ? (
          <IntComponent
            disabled={disabled}
            value={data.node.template[name].value ?? ""}
            onChange={(t) => {
              data.node.template[name].value = t;
              save();
            }}
          />
        ) : left === true && type === "prompt" ? (
          <PromptAreaComponent
            disabled={disabled}
            value={data.node.template[name].value ?? ""}
            onChange={(t: string) => {
              data.node.template[name].value = t;
              save();
            }}
          />
        ) : (
          <></>
        ))}
    </>
  );
}
