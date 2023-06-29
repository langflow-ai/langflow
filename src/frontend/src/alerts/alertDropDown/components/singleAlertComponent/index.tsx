import { Link } from "react-router-dom";
import { Transition } from "@headlessui/react";
import { useState } from "react";
import { SingleAlertComponentType } from "../../../../types/alerts";
import { X, CheckCircle2, Info, XCircle } from "lucide-react";

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
          className="flex bg-error-background rounded-md p-3 mb-2 mx-2"
          key={dropItem.id}
        >
          <div className="flex-shrink-0">
            <XCircle
              className="h-5 w-5 text-status-red"
              aria-hidden="true"
            />
          </div>
          <div className="ml-3">
            <h3 className="text-sm break-words font-medium text-error-foreground">
              {dropItem.title}
            </h3>
            {dropItem.list ? (
              <div className="mt-2 text-sm text-error-foreground">
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
                className="inline-flex rounded-md bg-red-50 p-1.5 text-status-red"
              >
                <span className="sr-only">Dismiss</span>
                <X className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>
          </div>
        </div>
      ) : type === "notice" ? (
        <div
          className="flex rounded-md bg-blue-50 p-3 mb-2 mx-2"
          key={dropItem.id}
        >
          <div className="flex-shrink-0">
            <Info
              className="h-5 w-5 text-medium-dark-blue"
              aria-hidden="true"
            />
          </div>
          <div className="ml-3 flex-1 md:flex md:justify-between">
            <p className="text-sm text-medium-dark-blue">
              {dropItem.title}
            </p>
            <p className="mt-3 text-sm md:mt-0 md:ml-6">
              {dropItem.link ? (
                <Link
                  to={dropItem.link}
                  className="whitespace-nowrap font-medium text-medium-dark-blue hover:text-ring"
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
                className="inline-flex rounded-md bg-blue-50 p-1.5 text-medium-dark-blue "
              >
                <span className="sr-only">Dismiss</span>
                <X className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div
          className="flex bg-green-50  p-3 mb-2 mx-2 rounded-md"
          key={dropItem.id}
        >
          <div className="flex-shrink-0">
            <CheckCircle2
              className="h-5 w-5 text-status-green"
              aria-hidden="true"
            />
          </div>
          <div className="ml-3">
            <p className="text-sm font-medium text-success-foreground">
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
                className="inline-flex rounded-md bg-success-background p-1.5 text-status-green"
              >
                <span className="sr-only">Dismiss</span>
                <X className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>
          </div>
        </div>
      )}
    </Transition>
  );
}
