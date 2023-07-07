import { Transition } from "@headlessui/react";
import { MessagesSquare } from "lucide-react";

import { useContext } from "react";
import {
  CHAT_CANNOT_OPEN_DESCRIPTION,
  CHAT_CANNOT_OPEN_TITLE,
  FLOW_NOT_BUILT_DESCRIPTION,
  FLOW_NOT_BUILT_TITLE,
} from "../../../constants";
import { alertContext } from "../../../contexts/alertContext";

export default function ChatTrigger({ open, setOpen, isBuilt, canOpen }) {
  const { setErrorData } = useContext(alertContext);

  function handleClick() {
    if (isBuilt) {
      if (canOpen) {
        setOpen(true);
      } else {
        setErrorData({
          title: CHAT_CANNOT_OPEN_TITLE,
          list: [CHAT_CANNOT_OPEN_DESCRIPTION],
        });
      }
    } else {
      setErrorData({
        title: FLOW_NOT_BUILT_TITLE,
        list: [FLOW_NOT_BUILT_DESCRIPTION],
      });
    }
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
        className={
          "shadow-round-btn-shadow hover:shadow-round-btn-shadow message-button " +
          (!isBuilt || !canOpen ? "cursor-not-allowed" : "cursor-pointer")
        }
      >
        <div className="flex gap-3">
          <MessagesSquare
            className={
              "h-6 w-6 transition-all " +
              (isBuilt && canOpen
                ? "message-button-icon"
                : "disabled-message-button-icon")
            }
            style={{ color: "white" }}
            strokeWidth={1.5}
          />
        </div>
      </button>
    </Transition>
  );
}
