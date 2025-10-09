//import LangflowLogoColor from "@/assets/LangflowLogocolor.svg?react";

import { PlaygroundComponent } from "@/components/core/playgroundComponent/playground-component";
import type { IOModalPropsType } from "../../types/components";
import BaseModal from "../baseModal";

export default function IOModal({
  children,
  open,
  setOpen,
  disable,
  isPlayground,
}: IOModalPropsType): JSX.Element {
  return (
    <BaseModal
      open={open}
      setOpen={setOpen}
      disable={disable}
      type={isPlayground ? "full-screen" : undefined}
      size="x-large"
      className="!rounded-[12px] p-0"
    >
      <BaseModal.Trigger>{children}</BaseModal.Trigger>
      {/* TODO ADAPT TO ALL TYPES OF INPUTS AND OUTPUTS */}
      <BaseModal.Content overflowHidden className="h-full">
        {open && <PlaygroundComponent />}
      </BaseModal.Content>
    </BaseModal>
  );
}
