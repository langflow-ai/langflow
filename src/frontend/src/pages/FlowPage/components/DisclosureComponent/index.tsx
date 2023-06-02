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
            <Disclosure.Button className="select-none bg-gray-50 dark:bg-gray-700/60 dark:border-y-gray-600 w-full flex justify-between items-center -mt-px px-3 py-2 border-y border-y-gray-200">
              <div className="flex gap-4">
                <Icon className="w-6 text-gray-800 dark:text-white/80" />
                <span className="flex items-center text-sm text-gray-800 dark:text-white/80 font-medium">
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
                    } h-4 w-4 text-gray-800 dark:text-white`}
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
