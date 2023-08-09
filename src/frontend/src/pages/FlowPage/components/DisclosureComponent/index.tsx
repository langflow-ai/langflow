import { Disclosure } from "@headlessui/react";
import IconComponent from "../../../../components/genericIconComponent";
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
            <Disclosure.Button className="components-disclosure-arrangement">
              <div className="flex gap-4">
                <Icon strokeWidth={1.5} size={22} className="text-primary" />
                <span className="components-disclosure-title">{title}</span>
              </div>
              <div className="components-disclosure-div">
                {buttons.map((btn, index) => (
                  <button key={index} onClick={btn.onClick}>
                    {btn.Icon}
                  </button>
                ))}
                <div>
                  <IconComponent
                    name="ChevronRight"
                    className={`${
                      open || openDisc ? "rotate-90 transform" : ""
                    } h-4 w-4 text-foreground`}
                  />
                </div>
              </div>
            </Disclosure.Button>
          </div>
          <Disclosure.Panel as="div" static={openDisc}>
            {children}
          </Disclosure.Panel>
        </>
      )}
    </Disclosure>
  );
}
