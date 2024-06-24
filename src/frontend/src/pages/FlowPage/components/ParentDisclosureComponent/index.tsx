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
              <div className="flex items-baseline gap-1 align-baseline">
                <span className="parent-disclosure-title">{title}</span>
                {title === "Experimental" && (
                  <div className="h-fit rounded-full bg-beta-background px-2 py-1 text-xs/3 font-semibold text-beta-foreground-soft">
                    BETA
                  </div>
                )}
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
