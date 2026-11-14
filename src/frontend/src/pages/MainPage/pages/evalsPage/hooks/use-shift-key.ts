import { useEffect, useState } from "react";

/** Whether Shift is held, for the multi-select tables (same behavior as Files and Knowledge). */
export function useShiftKey(): boolean {
  const [pressed, setPressed] = useState(false);
  useEffect(() => {
    const down = (event: KeyboardEvent) => {
      if (event.key === "Shift") setPressed(true);
    };
    const up = (event: KeyboardEvent) => {
      if (event.key === "Shift") setPressed(false);
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, []);
  return pressed;
}
