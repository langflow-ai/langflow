import { useState } from "react";
import CodeAreaComponent from "../../../../components/codeAreaComponent";
import Dropdown from "../../../../components/dropdownComponent";
import FloatComponent from "../../../../components/floatComponent";
import InputComponent from "../../../../components/inputComponent";
import InputFileComponent from "../../../../components/inputFileComponent";
import InputListComponent from "../../../../components/inputListComponent";
import IntComponent from "../../../../components/intComponent";
import PromptAreaComponent from "../../../../components/promptComponent";
import TextAreaComponent from "../../../../components/textAreaComponent";
import ToggleComponent from "../../../../components/toggleComponent";
import { classNames } from "../../../../utils/utils";

export default function ModalField({
  data,
  title,
  required,
  id,
  name,
  type,
  index,
}) {
  const [enabled, setEnabled] = useState(
    data.node.template[name]?.value ?? false
  );
  const display =
    type === "str" ||
    type === "int" ||
    type === "prompt" ||
    type === "bool" ||
    type === "float" ||
    type === "file" ||
    type === "code";

  return (
    <div
      className={classNames(
        "flex w-full flex-row items-center justify-between",
        display ? "" : "hidden",
        Object.keys(data.node.template).filter(
          (t) =>
            t.charAt(0) !== "_" &&
            data.node.template[t].advanced &&
            data.node.template[t].show
        ).length -
          1 ===
          index
          ? "pb-4"
          : ""
      )}
    >
      {display && (
        <div>
          <span className="mx-2">{title}</span>
          <span className="text-status-red">{required ? " *" : ""}</span>
        </div>
      )}

      {type === "str" && !data.node.template[name].options ? (
        <div className="w-1/2">
          {data.node.template[name].list ? (
            <InputListComponent
              disabled={false}
              value={
                !data.node.template[name].value ||
                data.node.template[name].value === ""
                  ? [""]
                  : data.node.template[name].value
              }
              onChange={(t: string[]) => {
                data.node.template[name].value = t;
              }}
            />
          ) : data.node.template[name].multiline ? (
            <TextAreaComponent
              disabled={false}
              value={data.node.template[name].value ?? ""}
              onChange={(t: string) => {
                data.node.template[name].value = t;
              }}
            />
          ) : (
            <InputComponent
              disabled={false}
              password={data.node.template[name].password ?? false}
              value={data.node.template[name].value ?? ""}
              onChange={(t) => {
                data.node.template[name].value = t;
              }}
            />
          )}
        </div>
      ) : type === "bool" ? (
        <div className="ml-auto">
          {" "}
          <ToggleComponent
            disabled={false}
            enabled={enabled}
            setEnabled={(t) => {
              data.node.template[name].value = t;
              setEnabled(t);
            }}
            size="small"
          />
        </div>
      ) : type === "float" ? (
        <div className="w-1/2">
          <FloatComponent
            disabled={false}
            value={data.node.template[name].value ?? ""}
            onChange={(t) => {
              data.node.template[name].value = t;
            }}
          />
        </div>
      ) : type === "str" && data.node.template[name].options ? (
        <div className="w-1/2">
          <Dropdown
            options={data.node.template[name].options}
            onSelect={(newValue) => (data.node.template[name].value = newValue)}
            value={data.node.template[name].value ?? "Choose an option"}
          ></Dropdown>
        </div>
      ) : type === "int" ? (
        <div className="w-1/2">
          <IntComponent
            disabled={false}
            value={data.node.template[name].value ?? ""}
            onChange={(t) => {
              data.node.template[name].value = t;
            }}
          />
        </div>
      ) : type === "file" ? (
        <div className="w-1/2">
          <InputFileComponent
            disabled={false}
            value={data.node.template[name].value ?? ""}
            onChange={(t: string) => {
              data.node.template[name].value = t;
            }}
            fileTypes={data.node.template[name].fileTypes}
            suffixes={data.node.template[name].suffixes}
            onFileChange={(t: string) => {
              data.node.template[name].file_path = t;
            }}
          ></InputFileComponent>
        </div>
      ) : type === "prompt" ? (
        <div className="w-1/2">
          <PromptAreaComponent
            field_name={name}
            disabled={false}
            value={data.node.template[name].value ?? ""}
            onChange={(t: string) => {
              data.node.template[name].value = t;
            }}
          />
        </div>
      ) : type === "code" ? (
        <div className="w-1/2">
          <CodeAreaComponent
            dynamic={data.node.template[name].dynamic ?? false}
            setNodeClass={(nodeClass) => {
              data.node = nodeClass;
            }}
            nodeClass={data.node}
            disabled={false}
            value={data.node.template[name].value ?? ""}
            onChange={(t: string) => {
              data.node.template[name].value = t;
            }}
          />
        </div>
      ) : (
        <div className="hidden"></div>
      )}
    </div>
  );
}
