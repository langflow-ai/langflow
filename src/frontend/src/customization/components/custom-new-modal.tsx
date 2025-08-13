import IOModal from "@/modals/IOModal/playground-modal";
import type { IOModalPropsType } from "@/types/components";

export function CustomIOModal({
  children,
  open,
  setOpen,
  disable,
  isPlayground,
  canvasOpen,
  playgroundPage,
}: IOModalPropsType) {
  return (
    <IOModal
      children={children}
      open={open}
      setOpen={setOpen}
      disable={disable}
      isPlayground={isPlayground}
      canvasOpen={canvasOpen}
      playgroundPage={playgroundPage}
    />
  );
}
