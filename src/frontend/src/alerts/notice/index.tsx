import { Transition } from "@headlessui/react";
import { InformationCircleIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { NoticeAlertType } from "../../types/alerts";

export default function NoticeAlert({
  title,
  link = "",
  id,
  removeAlert,
}: NoticeAlertType) {
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
        className="mt-6 w-96 rounded-md bg-blue-50 p-4 shadow-xl dark:bg-blue-900"
      >
        <div className="flex">
          <div className="flex-shrink-0">
            <InformationCircleIcon
              className="h-5 w-5 text-blue-400 dark:text-blue-50"
              aria-hidden="true"
            />
          </div>
          <div className="ml-3 flex-1 md:flex md:justify-between">
            <p className="text-sm text-blue-700 dark:text-white/80">{title}</p>
            <p className="mt-3 text-sm md:ml-6 md:mt-0">
              {link !== "" ? (
                <Link
                  to={link}
                  className="hover:dark:text-blue-10 whitespace-nowrap font-medium text-blue-700 hover:text-blue-600 dark:text-blue-50"
                >
                  Details
                </Link>
              ) : (
                <></>
              )}
            </p>
          </div>
        </div>
      </div>
    </Transition>
  );
}
