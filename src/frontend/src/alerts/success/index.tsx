import { Transition } from "@headlessui/react";
import { useEffect, useState } from "react";
import IconComponent from "../../components/common/genericIconComponent";
import { SuccessAlertType } from "../../types/alerts";

export default function SuccessAlert({
  title,
  id,
  removeAlert,
}: SuccessAlertType): JSX.Element {
  const [show, setShow] = useState(true);
  useEffect(() => {
    if (show) {
      setTimeout(() => {
        setShow(false);
        setTimeout(() => {
          removeAlert(id);
        }, 500);
      }, 5000);
    }
  }, [id, removeAlert, show]);
  return (
    <Transition
      show={show}
      enter="transition-transform duration-500 ease-out"
      enterFrom={"transform translate-x-[-100%]"}
      enterTo={"transform translate-x-0"}
      leave="transition-transform duration-500 ease-in"
      leaveFrom={"transform translate-x-0"}
      leaveTo={"transform translate-x-[-100%]"}
    >
      <div
        onClick={() => {
          setShow(false);
          removeAlert(id);
        }}
        className="success-alert noflow nowheel nopan nodelete nodrag"
      >
        <div className="flex">
          <div className="shrink-0">
            <IconComponent
              name="CheckCircle2"
              className="success-alert-icon"
              aria-hidden="true"
            />
          </div>
          <div className="ml-3">
            <p className="success-alert-message line-clamp-2">{title}</p>
          </div>
        </div>
      </div>
    </Transition>
  );
}
