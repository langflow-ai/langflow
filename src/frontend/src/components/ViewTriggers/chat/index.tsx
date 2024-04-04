import { Transition } from "@headlessui/react";

import IconComponent from "../../genericIconComponent";

export default function ChatTrigger({}): JSX.Element {
  return (
    <Transition
      show={true}
      appear={true}
      enter="transition ease-out duration-300"
      enterFrom="translate-y-96"
      enterTo="translate-y-0"
      leave="transition ease-in duration-300"
      leaveFrom="translate-y-0"
      leaveTo="translate-y-96"
    >
      <button
        className={
          "shadow-round-btn-shadow hover:shadow-round-btn-shadow message-button cursor-pointer"
        }
      >
        <div className="flex gap-3">
          <IconComponent
            name="Zap"
            className={"message-button-icon h-6 w-6 transition-all"}
          />
        </div>
      </button>
    </Transition>
  );
}
