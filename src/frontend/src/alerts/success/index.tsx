import { Transition } from "@headlessui/react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import IconComponent from "../../components/common/genericIconComponent";
import type { SuccessAlertType } from "../../types/alerts";

export default function SuccessAlert({
  title,
  id,
  removeAlert,
}: SuccessAlertType): JSX.Element {
  const { t } = useTranslation();
  const [show, setShow] = useState(true);
  const handleDismiss = () => {
    setShow(false);
    removeAlert(id);
  };
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
        onClick={handleDismiss}
        className="success-alert noflow nowheel nopan nodelete nodrag"
      >
        <div className="flex">
          <div className="flex-shrink-0">
            <IconComponent
              name="CheckCircle2"
              className="success-alert-icon"
              aria-hidden="true"
            />
          </div>
          <div className="ml-3">
            <p className="success-alert-message line-clamp-3">{title}</p>
          </div>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              handleDismiss();
            }}
            aria-label={t("alerts.dismissAlert")}
            className="ml-auto flex-shrink-0 self-start"
          >
            <IconComponent name="X" className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </div>
    </Transition>
  );
}
