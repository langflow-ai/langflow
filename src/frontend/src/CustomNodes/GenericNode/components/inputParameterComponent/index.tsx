import { Handle, Position, useUpdateNodeInternals } from "reactflow";
import Tooltip from "../../../../components/TooltipComponent";
import { classNames, isValidConnection } from "../../../../utils";
import { useContext, useEffect, useRef, useState } from "react";
import InputComponent from "../../../../components/inputComponent";
import ToggleComponent from "../../../../components/toggleComponent";
import InputListComponent from "../../../../components/inputListComponent";
import TextAreaComponent from "../../../../components/textAreaComponent";
import { typesContext } from "../../../../contexts/typesContext";
import { InputParameterComponentType } from "../../../../types/components";
import FloatComponent from "../../../../components/floatComponent";
import Dropdown from "../../../../components/dropdownComponent";
import CodeAreaComponent from "../../../../components/codeAreaComponent";
import InputFileComponent from "../../../../components/inputFileComponent";
import { TabsContext } from "../../../../contexts/tabsContext";
import IntComponent from "../../../../components/intComponent";
import PromptAreaComponent from "../../../../components/promptComponent";
import HandleComponent from "../parameterComponent/components/handleComponent";

export default function InputParameterComponent({
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
}: InputParameterComponentType) {
  const ref = useRef(null);
  const updateNodeInternals = useUpdateNodeInternals();
  const [flowHandlePosition, setFlowHandlePosition] = useState(0);
  useEffect(() => {
    if (ref.current && ref.current.offsetTop && ref.current.clientHeight) {
      setFlowHandlePosition(
        ref.current.offsetTop + ref.current.clientHeight / 2
      );
      updateNodeInternals(data.id);
    }
  }, [data.id, ref, updateNodeInternals, ref.current]);

  useEffect(() => {
    updateNodeInternals(data.id);
  }, [data.id, flowHandlePosition, updateNodeInternals]);

  return (
    <div
      ref={ref}
      className={
        "mt-5 flex w-full flex-wrap items-center justify-between bg-gray-50 px-5 py-2 dark:bg-gray-800 dark:text-white "
      }
    >
      <HandleComponent
        handleDisabled={handleDisabled}
        position={flowHandlePosition}
        tooltipTitle={`Type: ${data.node.base_classes.join(" | ")}`}
        data={data}
        color={color}
        title={title}
        name="Input"
        fill={true}
        id={"Text|Input|" + data.id}
        left={true}
        type={type}
        required={required}
      />
      <HandleComponent
        handleDisabled={handleDisabled}
        data={data}
        position={flowHandlePosition}
        fill={true}
        color={color}
        title={"Output"}
        tooltipTitle={tooltipTitle}
        id={[data.type, data.id, ...data.node.base_classes].join("|")}
        type={data.node.base_classes.join("|")}
        left={false}
        required={required}
      />
    </div>
  );
}
