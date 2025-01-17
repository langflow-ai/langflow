import { CustomLink } from "@/customization/components/custom-link";
import { Transition } from "@headlessui/react";
import { useEffect, useState } from "react";
import IconComponent from "../../components/common/genericIconComponent";
import { NoticeAlertType } from "../../types/alerts";

export default function NoticeAlert({
  title,
  link,
  id,
  removeAlert,
}: NoticeAlertType): JSX.Element {
  const [show, setShow] = useState(true);

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      setShow(false);
      // Wait for the leave transition before calling removeAlert
      setTimeout(() => {
        removeAlert(id);
      }, 500); // match the duration of the leave transition
    }, 5000); // auto-dismiss alert after 5 seconds

    return () => clearTimeout(timeoutId); // Cleanup timeout on component unmount or re-render
  }, [id, removeAlert]);

  const handleClick = () => {
    setShow(false);
    // Wait for the leave transition before calling removeAlert
    setTimeout(() => {
      removeAlert(id);
    }, 500); // Ensure the alert is removed after the animation
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
      <div
        onClick={handleClick}
        className="noflow nowheel nopan nodelete nodrag mt-6 w-96 rounded-md bg-info-background p-4 shadow-xl"
      >
        <div className="flex">
          <div className="flex-shrink-0 cursor-help">
            <IconComponent
              name="Info"
              className="h-5 w-5 text-status-blue"
              aria-hidden="true"
            />
          </div>
          <div className="ml-3 flex-1 md:flex md:justify-between">
            <p className="text-sm text-info-foreground word-break-break-word">
              {title}
            </p>
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
        </div>
      </div>
    </Transition>
  );
}
