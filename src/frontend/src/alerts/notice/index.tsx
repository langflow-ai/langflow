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
        className="noflow nowheel nopan nodelete nodrag bg-info-background mt-6 w-96 rounded-md p-4 shadow-xl"
      >
        <div className="flex">
          <div className="flex-shrink-0 cursor-help">
            <IconComponent
              name="Info"
              className="text-status-blue h-5 w-5"
              aria-hidden="true"
            />
          </div>
          <div className="ml-3 flex-1 md:flex md:justify-between">
            <p className="text-info-foreground word-break-break-word text-sm">
              {title}
            </p>
            <p className="mt-3 text-sm md:mt-0 md:ml-6">
              {link && (
                <CustomLink
                  to={link}
                  className="text-info-foreground hover:text-accent-foreground font-medium whitespace-nowrap"
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
