import { CustomLink } from "@/customization/components/custom-link";
import { Transition } from "@headlessui/react";
import { useEffect, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import IconComponent from "../../components/common/genericIconComponent";
import { NoticeAlertType } from "../../types/alerts";

export default function NoticeAlert({
  title,
  list = [],
  id,
  link,
  removeAlert,
}: NoticeAlertType): JSX.Element {
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
      <div
        onClick={handleClick}
        className="noflow nowheel nopan nodelete nodrag bg-info-background mt-6 w-96 rounded-md p-4 shadow-xl"
      >
        <div className="flex">
          <div className="shrink-0 cursor-help">
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
