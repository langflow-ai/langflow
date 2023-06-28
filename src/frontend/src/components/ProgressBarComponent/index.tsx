import { ReactElement, useContext, useEffect, useRef, useState } from "react";
import { ProgressBarType } from "../../types/components";
import { Progress } from "../../components/ui/progress";
import { progressContext } from "../../contexts/ProgressContext";
import { setInterval } from "timers/promises";

export default function ProgressBarComponent({
  value,
  children,
}: ProgressBarType) {
  const ref = useRef(0);
  const reff = useRef();
  const { progress } = useContext(progressContext);

  useEffect(() => {
    ref.current = progress * 100;
    console.log(progress);
  }, [progress]);

  return <Progress className="h-2.5" value={ref.current} />;
}
