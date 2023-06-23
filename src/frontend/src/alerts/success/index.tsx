import { Transition } from "@headlessui/react";
import { useEffect, useState } from "react";
import { SuccessAlertType } from "../../types/alerts";
import { CheckCircle2 } from "lucide-react";

export default function SuccessAlert({
  title,
  id,
  removeAlert,
}: SuccessAlertType) {
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
        className="rounded-md w-96 mt-6 shadow-xl bg-green-50 dark:bg-green-900 p-4"
      >
        <div className="flex">
          <div className="flex-shrink-0">
            <CheckCircle2
              className="h-5 w-5 text-green-400 dark:text-green-50"
              aria-hidden="true"
            />
          </div>
          <div className="ml-3">
            <p className="text-sm font-medium text-green-800 dark:text-white/80">
              {title}
            </p>
          </div>
        </div>
      </div>
    </Transition>
  );
}
