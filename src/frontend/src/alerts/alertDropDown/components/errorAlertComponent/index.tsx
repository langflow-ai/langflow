import ForwardedIconComponent from "@/components/genericIconComponent";
import { AlertComponentType } from "@/types/alerts";
import handleClass from "../singleAlertComponent/utils/handle-class";
import { useRef } from "react";

export default function ErrorAlertComponent({ alert, setShow, removeAlert, isDropdown }: AlertComponentType) {

    const classes = handleClass(isDropdown);
    return (
        <div className={`${classes} bg-error-background`} key={alert.id}>
        <div className="flex-shrink-0">
          <ForwardedIconComponent
            name="XCircle"
            className="h-5 w-5 text-status-red"
            aria-hidden="true"
          />
        </div>
        <div className="ml-3">
          <h3 className="text-sm font-medium text-error-foreground word-break-break-word">
            {alert.title}
          </h3>
          {alert.list ? (
            <div className="mt-2 text-sm text-error-foreground">
              <ul className="list-disc space-y-1 pl-5">
                {alert.list.map((item, idx) => (
                  <li className="word-break-break-word" key={idx}>
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
                  removeAlert(alert.id);
                }, 500);
              }}
              className="inline-flex rounded-md p-1.5 text-status-red"
            >
              <span className="sr-only">Dismiss</span>
              <ForwardedIconComponent
                name="X"
                className="h-4 w-4 text-error-foreground"
                aria-hidden="true"
              />
            </button>
          </div>
        </div>
      </div>
    );
}
