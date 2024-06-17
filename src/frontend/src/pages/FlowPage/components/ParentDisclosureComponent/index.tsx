import { Disclosure } from "@headlessui/react";
import IconComponent from "../../../../components/genericIconComponent";
import { DisclosureComponentType } from "../../../../types/components";

export default function ParentDisclosureComponent({
  button: { title, Icon, buttons = [] },
  children,
  defaultOpen,
  testId,
}: DisclosureComponentType): JSX.Element {
  return (
    <Disclosure as="div" defaultOpen={defaultOpen} key={title}>
      {({ open }) => (
        <>
          <div>
            <Disclosure.Button
              className="parent-disclosure-arrangement"
              data-testid={testId}
            >
              <div className="flex gap-4">
                <span className="parent-disclosure-title">{title}</span>
              </div>
              <div className="components-disclosure-div">
                {buttons.map((btn, index) => (
                  <button key={index} onClick={btn.onClick}>
                    {btn.Icon}
                  </button>
                ))}
                <div>
                  <IconComponent
                    name="ChevronsUpDownIcon"
                    className={`${
                      open || defaultOpen ? "" : ""
                    } h-4 w-4 text-foreground`}
                  />
                </div>
              </div>
            </Disclosure.Button>
          </div>
          <Disclosure.Panel as="div">{children}</Disclosure.Panel>
        </>
      )}
    </Disclosure>
  );
}
