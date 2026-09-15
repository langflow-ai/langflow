import { Transition } from "@headlessui/react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { CustomLink } from "@/customization/components/custom-link";
import IconComponent from "../../components/common/genericIconComponent";
import type { NoticeAlertType } from "../../types/alerts";

export default function NoticeAlert({
  title,
  list = [],
  id,
  link,
  removeAlert,
}: NoticeAlertType): JSX.Element {
  const { t } = useTranslation();
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

  const handleClick = () => {
    setShow(false);
    setTimeout(() => {
      removeAlert(id);
    }, 500);
  };

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
      <div className="noflow nowheel nopan nodelete nodrag mt-6 w-96 rounded-md bg-info-background p-4 shadow-xl">
        <div className="flex">
          <div className="flex-shrink-0 cursor-help">
            <IconComponent
              name="Info"
              className="h-5 w-5 text-status-blue"
              aria-hidden="true"
            />
          </div>
          <div className="ml-3 min-w-0 flex-1">
            <p className="text-sm text-info-foreground word-break-break-word">
              {title}
            </p>
            {list.length > 0 && (
              <div
                role="region"
                aria-label={title}
                tabIndex={0}
                className="mt-2 max-h-48 overflow-y-auto text-sm text-info-foreground"
              >
                {list.map((item, index) => (
                  <p key={index} className="whitespace-pre-wrap break-words">
                    {item}
                  </p>
                ))}
              </div>
            )}
            <p className="mt-3 text-sm md:ml-6 md:mt-0">
              {link && (
                <CustomLink
                  to={link}
                  className="whitespace-nowrap font-medium text-info-foreground hover:text-accent-foreground"
                >
                  Details
                </CustomLink>
              )}
            </p>
          </div>
          <button
            type="button"
            onClick={handleClick}
            aria-label={t("alerts.dismissAlert")}
            className="ml-3 flex-shrink-0 self-start"
          >
            <IconComponent name="X" className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </div>
    </Transition>
  );
}
