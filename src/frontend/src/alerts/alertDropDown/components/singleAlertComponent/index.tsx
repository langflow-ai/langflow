import { Transition } from "@headlessui/react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import IconComponent from "../../../../components/genericIconComponent";
import { SingleAlertComponentType } from "../../../../types/alerts";
import handleClass from "./utils/handle-class";
import RenderAlertComponent from "../RenderAlert";

export default function SingleAlert({
  dropItem,
  removeAlert,
  isDropdown = true,
}: SingleAlertComponentType): JSX.Element {
  const [show, setShow] = useState(true);

  useEffect(() => {
    if (show && !isDropdown) {
      setTimeout(() => {
        setShow(false);
        setTimeout(() => {
          removeAlert(dropItem.id);
        }, 500);
      }, 5000);
    }
  }, [dropItem.id, removeAlert, show]);

  return (
    <Transition
      //@ts-ignore
      className="noflow nowheel nopan nodelete nodrag relative"
      show={show}
      appear={true}
      enter="transition-transform duration-500 ease-out"
      enterFrom={"transform translate-x-[-100%]"}
      enterTo={"transform translate-x-0"}
      leave="transition-transform duration-500 ease-in"
      leaveFrom={"transform translate-x-0"}
      leaveTo={"transform translate-x-[-100%]"}
    >
      <div>
        <RenderAlertComponent
          alert={dropItem}
          setShow={setShow}
          removeAlert={removeAlert}
          isDropdown={isDropdown}
        />
      </div>
    </Transition>
  );
}
