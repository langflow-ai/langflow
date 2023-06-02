import { useContext, useState } from "react";
import { TabsContext } from "../../../../contexts/tabsContext";
import InputListComponent from "../../../../components/inputListComponent";
import Dropdown from "../../../../components/dropdownComponent";
import TextAreaComponent from "../../../../components/textAreaComponent";
import InputComponent from "../../../../components/inputComponent";
import ToggleComponent from "../../../../components/toggleComponent";
import FloatComponent from "../../../../components/floatComponent";
import IntComponent from "../../../../components/intComponent";
import InputFileComponent from "../../../../components/inputFileComponent";
import PromptAreaComponent from "../../../../components/promptComponent";
import CodeAreaComponent from "../../../../components/codeAreaComponent";
import { classNames } from "../../../../utils";

export default function ModalField({
  data,
  title,
  required,
  id,
  name,
  type,
  index,
}) {
  const { save } = useContext(TabsContext);
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
        "flex flex-row w-full items-center justify-between",
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
          <span className="mx-2 dark:text-gray-300">{title}</span>
          <span className="text-red-600">{required ? " *" : ""}</span>
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
                save();
              }}
            />
          ) : data.node.template[name].multiline ? (
            <TextAreaComponent
              disabled={false}
              value={data.node.template[name].value ?? ""}
              onChange={(t: string) => {
                data.node.template[name].value = t;
                save();
              }}
            />
          ) : (
            <InputComponent
              disabled={false}
              password={data.node.template[name].password ?? false}
              value={data.node.template[name].value ?? ""}
              onChange={(t) => {
                data.node.template[name].value = t;
                save();
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
              save();
            }}
          />
        </div>
      ) : type === "float" ? (
        <div className="w-1/2">
          <FloatComponent
            disabled={false}
            value={data.node.template[name].value ?? ""}
            onChange={(t) => {
              data.node.template[name].value = t;
              save();
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
              save();
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
              data.node.template[name].content = t;
              save();
            }}
          ></InputFileComponent>
        </div>
      ) : type === "prompt" ? (
        <div className="w-1/2">
          <PromptAreaComponent
            disabled={false}
            value={data.node.template[name].value ?? ""}
            onChange={(t: string) => {
              data.node.template[name].value = t;
              save();
            }}
          />
        </div>
      ) : type === "code" ? (
        <div className="w-1/2">
          <CodeAreaComponent
            disabled={false}
            value={data.node.template[name].value ?? ""}
            onChange={(t: string) => {
              data.node.template[name].value = t;
              save();
            }}
          />
        </div>
      ) : (
        <div className="hidden"></div>
      )}
    </div>
  );
}
