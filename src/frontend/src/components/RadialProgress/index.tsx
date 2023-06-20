import { useContext, useEffect, useRef } from "react";
import { RadialProgressType } from "../../types/components";
import { Progress } from "../ui/progress";
import { progressContext } from "../../contexts/ProgressContext";

export default function RadialProgressComponent({
  value,
  color,
}: RadialProgressType) {
  const ref = useRef(0);
  const { progress } = useContext(progressContext);

  useEffect(() => {
    ref.current = progress * 100;
  }, [progress]);

  const style = {
    "--value": ref.current,
    "--size": "1.5rem",
    "--thickness": "2px",
  } as React.CSSProperties;

  return (
    <div className={"radial-progress " + color} style={style}>
      <strong className="text-[8px]">{ref.current}%</strong>
    </div>
  );
}
