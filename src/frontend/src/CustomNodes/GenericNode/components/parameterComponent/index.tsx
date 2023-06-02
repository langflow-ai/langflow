import { useUpdateNodeInternals } from "reactflow";
import { useEffect, useRef, useState } from "react";
import { ParameterComponentType } from "../../../../types/components";
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
  debugger;
  useEffect(() => {
    if (ref.current && ref.current.offsetTop && ref.current.clientHeight) {
      setPosition(ref.current.offsetTop + ref.current.clientHeight / 2);
      updateNodeInternals(data.id);
    }
  }, [data.id, ref, ref.current, ref.current?.offsetTop, updateNodeInternals]);

  useEffect(() => {
    if (ref.current) updateNodeInternals(data.id);
  }, [data.id, position, updateNodeInternals]);

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
