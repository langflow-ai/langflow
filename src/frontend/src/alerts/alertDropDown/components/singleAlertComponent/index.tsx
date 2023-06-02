import {
  XCircleIcon,
  XMarkIcon,
  InformationCircleIcon,
  CheckCircleIcon,
} from "@heroicons/react/24/outline";
import { Link } from "react-router-dom";
import { Transition } from "@headlessui/react";
import { useState } from "react";
import { SingleAlertComponentType } from "../../../../types/alerts";

export default function SingleAlert({
  dropItem,
  removeAlert,
}: SingleAlertComponentType) {
  const [show, setShow] = useState(true);
  const type = dropItem.type;

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
      {type === "error" ? (
        <div
          className="flex bg-red-50 dark:bg-red-900 rounded-md p-3 mb-2 mx-2"
          key={dropItem.id}
        >
          <div className="flex-shrink-0">
            <XCircleIcon
              className="h-5 w-5 text-red-400 dark:text-red-50"
              aria-hidden="true"
            />
          </div>
          <div className="ml-3">
            <h3 className="text-sm break-words font-medium text-red-800 dark:text-white/80">
              {dropItem.title}
            </h3>
            {dropItem.list ? (
              <div className="mt-2 text-sm text-red-700 dark:text-red-50">
                <ul className="list-disc space-y-1 pl-5">
                  {dropItem.list.map((item, idx) => (
                    <li className="break-words" key={idx}>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <></>
            )}
          </div>
          <div className="ml-auto pl-3">
            <div className="-mx-1.5 -my-1.5">
              <button
                type="button"
                onClick={() => {
                  setShow(false);
                  setTimeout(() => {
                    removeAlert(dropItem.id);
                  }, 500);
                }}
                className="inline-flex rounded-md bg-red-50 dark:bg-transparent p-1.5 text-red-500 dark:text-red-50"
              >
                <span className="sr-only">Dismiss</span>
                <XMarkIcon className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>
          </div>
        </div>
      ) : type === "notice" ? (
        <div
          className="flex rounded-md bg-blue-50 dark:bg-blue-900 p-3 mb-2 mx-2"
          key={dropItem.id}
        >
          <div className="flex-shrink-0">
            <InformationCircleIcon
              className="h-5 w-5 text-blue-400 dark:text-blue-50"
              aria-hidden="true"
            />
          </div>
          <div className="ml-3 flex-1 md:flex md:justify-between">
            <p className="text-sm text-blue-700 dark:text-white/80">
              {dropItem.title}
            </p>
            <p className="mt-3 text-sm md:mt-0 md:ml-6">
              {dropItem.link ? (
                <Link
                  to={dropItem.link}
                  className="whitespace-nowrap font-medium text-blue-700 dark:text-blue-50 dark:hover:text-blue-100 hover:text-blue-600"
                >
                  Details
                </Link>
              ) : (
                <></>
              )}
            </p>
          </div>
          <div className="ml-auto pl-3">
            <div className="-mx-1.5 -my-1.5">
              <button
                type="button"
                onClick={() => {
                  setShow(false);
                  setTimeout(() => {
                    removeAlert(dropItem.id);
                  }, 500);
                }}
                className="inline-flex rounded-md bg-blue-50 dark:bg-transparent p-1.5 text-blue-500 dark:text-blue-50"
              >
                <span className="sr-only">Dismiss</span>
                <XMarkIcon className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div
          className="flex bg-green-50 dark:bg-green-900 p-3 mb-2 mx-2 rounded-md"
          key={dropItem.id}
        >
          <div className="flex-shrink-0">
            <CheckCircleIcon
              className="h-5 w-5 text-green-400 dark:text-green-50"
              aria-hidden="true"
            />
          </div>
          <div className="ml-3">
            <p className="text-sm font-medium text-green-800 dark:bg-white/80">
              {dropItem.title}
            </p>
          </div>
          <div className="ml-auto pl-3">
            <div className="-mx-1.5 -my-1.5">
              <button
                type="button"
                onClick={() => {
                  setShow(false);
                  setTimeout(() => {
                    removeAlert(dropItem.id);
                  }, 500);
                }}
                className="inline-flex rounded-md bg-green-50 dark:bg-transparent p-1.5 text-green-500 dark:text-green-50"
              >
                <span className="sr-only">Dismiss</span>
                <XMarkIcon className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>
          </div>
        </div>
      )}
    </Transition>
  );
}
