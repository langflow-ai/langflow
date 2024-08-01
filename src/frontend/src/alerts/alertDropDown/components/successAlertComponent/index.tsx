import ForwardedIconComponent from "@/components/genericIconComponent";
import { AlertComponentType } from "@/types/alerts";
import handleClass from "../singleAlertComponent/utils/handle-class";

export default function SuccessAlertComponent({ alert, setShow, removeAlert, isDropdown }: AlertComponentType) {

    const classes = handleClass(isDropdown);

    return (
        <div className={`${classes} bg-success-background`} key={alert.id}>
          <div className="flex-shrink-0">
            <ForwardedIconComponent
              name="CheckCircle2"
              className="h-5 w-5 text-status-green"
              aria-hidden="true"
            />
          </div>
          <div className="ml-3">
            <p className="text-sm font-medium text-success-foreground">
              {alert.title}
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
                className="inline-flex rounded-md p-1.5 text-status-green"
              >
                <span className="sr-only">Dismiss</span>
                <ForwardedIconComponent
                  name="X"
                  className="h-4 w-4 text-success-foreground"
                  aria-hidden="true"
                />
              </button>
            </div>
          </div>
        </div>
    );
}
