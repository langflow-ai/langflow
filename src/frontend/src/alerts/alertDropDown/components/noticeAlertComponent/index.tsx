import ForwardedIconComponent from "@/components/genericIconComponent";
import { AlertComponentType } from "@/types/alerts";
import handleClass from "../singleAlertComponent/utils/handle-class";
import { Link } from "react-router-dom";

export default function NoticeAlertComponent({ alert, setShow, removeAlert, isDropdown }: AlertComponentType) {

    const classes = handleClass(isDropdown);
    return (
        <div className={`${classes} bg-info-background`} key={alert.id}>
          <div className="flex-shrink-0 cursor-help">
            <ForwardedIconComponent
              name="Info"
              className="h-5 w-5 text-status-blue"
              aria-hidden="true"
            />
          </div>
          <div className="ml-3 flex-1 md:flex md:justify-between">
            <p className="text-sm font-medium text-info-foreground">
              {alert.title}
            </p>
            <p className="mt-3 text-sm md:ml-6 md:mt-0">
              {alert.link ? (
                <Link
                  to={alert.link}
                  className="whitespace-nowrap font-medium text-info-foreground hover:text-accent-foreground"
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
                    removeAlert(alert.id);
                  }, 500);
                }}
                className="inline-flex rounded-md p-1.5 text-info-foreground"
              >
                <span className="sr-only">Dismiss</span>
                <ForwardedIconComponent
                  name="X"
                  className="h-4 w-4 text-info-foreground"
                  aria-hidden="true"
                />
              </button>
            </div>
          </div>
        </div>
    );
}
