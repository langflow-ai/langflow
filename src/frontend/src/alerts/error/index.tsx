import { Transition } from "@headlessui/react";
import { XCircleIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { useEffect, useState } from "react";
import { ErrorAlertType } from "../../types/alerts";

export default function ErrorAlert({
  title,
  list = [],
  id,
  removeAlert,
}: ErrorAlertType) {
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
      className="relative"
      show={show}
      appear={true}
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
          setTimeout(() => {
            removeAlert(id);
          }, 500);
        }}
        className="rounded-md w-96 mt-6 shadow-xl bg-red-50 dark:bg-red-900 p-4 cursor-pointer"
      >
        <div className="flex">
          <div className="flex-shrink-0">
            <XCircleIcon
              className="h-5 w-5 text-red-400 dark:text-red-50"
              aria-hidden="true"
            />
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-red-800 dark:text-white/80">
              {title}
            </h3>
            {list.length !== 0 ? (
              <div className="mt-2 text-sm text-red-700 dark:text-red-50">
                <ul className="list-disc space-y-1 pl-5">
                  {list.map((item, index) => (
                    <li key={index}>{item}</li>
                  ))}
                </ul>
              </div>
            ) : (
              <></>
            )}
          </div>
        </div>
      </div>
    </Transition>
  );
}
