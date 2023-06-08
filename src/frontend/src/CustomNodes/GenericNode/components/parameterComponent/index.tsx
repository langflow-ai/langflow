import { Handle, Position, useUpdateNodeInternals } from "reactflow";
import Tooltip from "../../../../components/TooltipComponent";
import {
  classNames,
  groupByFamily,
  isValidConnection,
  toFirstUpperCase,
} from "../../../../utils";
import { useContext, useEffect, useRef, useState } from "react";
import InputComponent from "../../../../components/inputComponent";
import ToggleComponent from "../../../../components/toggleComponent";
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
import { nodeNames, nodeIcons } from "../../../../utils";
import React from "react";
import { nodeColors } from "../../../../utils";
import ShadTooltip from "../../../../components/ShadTooltipComponent";
import HandleComponent from "./components/handleComponent";

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
  handleDisabled,
}: ParameterComponentType) {
  const ref = useRef<HTMLDivElement | null>(null);
  const updateNodeInternals = useUpdateNodeInternals();
  const [position, setPosition] = useState(0);
  useEffect(() => {
    if (ref.current && ref.current.offsetTop && ref.current.clientHeight) {
      setPosition(ref.current.offsetTop + ref.current.clientHeight / 2);
      updateNodeInternals(data.id);
    }
  }, [data.id, ref, ref.current, ref.current?.offsetTop, updateNodeInternals]);

  useEffect(() => {
    if (ref.current) updateNodeInternals(data.id);
  }, [data.id, position, updateNodeInternals]);

  const [enabled, setEnabled] = useState(
    data.node.template[name]?.value ?? false
  );
  const { reactFlowInstance } = useContext(typesContext);
  let disabled =
    reactFlowInstance?.getEdges().some((e) => e.targetHandle === id) ?? false;
  const { save } = useContext(TabsContext);
  const [myData, setMyData] = useState(useContext(typesContext).data);

  return (
    <div
      ref={ref}
      className={
        "mt-1 flex w-full flex-wrap items-center bg-gray-50 px-5 py-2 dark:bg-gray-800 dark:text-white" +
        (left ? " justify-between" : " justify-end")
      }
    >
      <HandleComponent
        handleDisabled={handleDisabled}
        position={position}
        left={left}
        id={id}
        data={data}
        tooltipTitle={tooltipTitle}
        title={title}
        color={color}
        type={type}
        name={name}
        required={required}
      />
    </div>
  );
}
