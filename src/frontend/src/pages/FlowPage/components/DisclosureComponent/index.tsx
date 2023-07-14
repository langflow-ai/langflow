import { Disclosure } from "@headlessui/react";
import { DisclosureComponentType } from "../../../../types/components";
import IconComponent from "../../../../components/genericIconComponent";

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
                {buttons.map((x, index) => (
                  <button key={index} onClick={x.onClick}>
                    {x.Icon}
                  </button>
                ))}
                <div>
                  <IconComponent
                    name="ChevronRight"
                    style={`${
                      open || openDisc ? "rotate-90 transform" : ""
                    } h-4 w-4 text-foreground`}
                    method="LUCIDE"
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
