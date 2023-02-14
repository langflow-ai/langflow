import {
  CpuChipIcon,
  PlusIcon,
  ChevronRightIcon,
  ArrowPathIcon,
  BoltIcon,
  ChevronDoubleRightIcon,
} from "@heroicons/react/24/outline";
import { Disclosure } from "@headlessui/react";
import { useState } from "react";
import { borderLColors } from "../../../../utils";

export default function DisclosureComponent({
  button: { title, Icon, buttons = [] },
  children,
}) {
  return (
    <Disclosure as="div" key={title}>
      {({ open }) => (
        <>
          <div>
            <div className="select-none bg-gray-50 w-full flex justify-between items-center -mt-px px-3 py-2 border border-gray-200">
              <div className="flex gap-4">
                <Icon className="w-6 text-gray-800" />
                <span className="flex items-center text-sm text-gray-800 font-medium">
                  {title}
                </span>
              </div>
              <div className="flex gap-2">
                {buttons.map((x, index)=>(
                  <button key={index} onClick={x.onClick}>
                    {x.Icon}
                  </button>
                ))}
                <Disclosure.Button as="button">
                  <ChevronRightIcon
                    className={`${
                      open ? "rotate-90 transform" : ""
                    } h-5 w-5 text-gray-800`}
                  />
                </Disclosure.Button>
              </div>
            </div>
          </div>
          <Disclosure.Panel as="div" className="-mt-px">
            {children}
          </Disclosure.Panel>
        </>
        
      )}
    </Disclosure>
  );
}
