import { ChevronRightIcon } from "@heroicons/react/24/solid";
import { Disclosure } from "@headlessui/react";
import { DisclosureComponentType } from "../../../../types/components";

export default function DisclosureComponent({
  button: { title, Icon, buttons = [] },
  children,
  openDisc,
}: DisclosureComponentType) {
  return (
    <Disclosure as="div" key={title}>
      {({ open }) => (
        <>
          <div>
            <Disclosure.Button className="select-none bg-muted dark:bg-almost-dark-gray/60 dark:border-y-medium-dark-gray w-full flex justify-between items-center -mt-px px-3 py-2 border-y border-y-light-gray">
              <div className="flex gap-4">
                <Icon className="w-6 text-dark-gray dark:text-white/80" />
                <span className="flex items-center text-sm text-dark-gray dark:text-white/80 font-medium">
                  {title}
                </span>
              </div>
              <div className="flex gap-2">
                {buttons.map((x, index) => (
                  <button key={index} onClick={x.onClick}>
                    {x.Icon}
                  </button>
                ))}
                <div>
                  <ChevronRightIcon
                    className={`${
                      open || openDisc ? "rotate-90 transform" : ""
                    } h-4 w-4 text-dark-gray dark:text-white`}
                  />
                </div>
              </div>
            </Disclosure.Button>
          </div>
          <Disclosure.Panel as="div" className="-mt-px" static={openDisc}>
            {children}
          </Disclosure.Panel>
        </>
      )}
    </Disclosure>
  );
}
