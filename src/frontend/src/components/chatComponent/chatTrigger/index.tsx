import { Transition } from "@headlessui/react";

import { useContext } from "react";
import { alertContext } from "../../../contexts/alertContext";
import { flowManagerContext } from "../../../contexts/flowManagerContext";
import { chatTriggerPropType } from "../../../types/components";
import IconComponent from "../../genericIconComponent";

export default function ChatTrigger({
  open,
  setOpen,
}: chatTriggerPropType): JSX.Element {
  const { setErrorData } = useContext(alertContext);
  const { inputTypes } = useContext(flowManagerContext);

  function handleClick(): void {
    setOpen(true);
    // if (isBuilt) {
    //   if (canOpen) {
    //     setOpen(true);
    //   } else {
    //     setErrorData({
    //       title: CHAT_CANNOT_OPEN_TITLE,
    //       list: [CHAT_CANNOT_OPEN_DESCRIPTION],
    //     });
    //   }
    // } else {
    //   setErrorData({
    //     title: FLOW_NOT_BUILT_TITLE,
    //     list: [FLOW_NOT_BUILT_DESCRIPTION],
    //   });
    // }
  }

  return (
    <Transition
      show={!open}
      appear={true}
      enter="transition ease-out duration-300"
      enterFrom="translate-y-96"
      enterTo="translate-y-0"
      leave="transition ease-in duration-300"
      leaveFrom="translate-y-0"
      leaveTo="translate-y-96"
    >
      <button
        onClick={handleClick}
        className="shadow-round-btn-shadow hover:shadow-round-btn-shadow message-button cursor-pointer"
      >
        <div className="flex gap-3">
          <IconComponent
            name={
              inputTypes.includes("ChatInput") ? "MessagesSquare" : "Sliders"
            }
            className="message-button-icon h-6 w-6 transition-all"
          />
        </div>
      </button>
    </Transition>
  );
}
