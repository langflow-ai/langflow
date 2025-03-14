import { Disclosure } from "@headlessui/react";
import IconComponent from "../../../../components/common/genericIconComponent";
import { DisclosureComponentType } from "../../../../types/components";

export default function ParentDisclosureComponent({
  button: { title, Icon, buttons = [], beta },
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
                <span className="text-sm font-medium">{title}</span>
                {beta && (
                  <div className="bg-beta-background text-beta-foreground-soft h-fit rounded-full px-2 py-1 text-xs/3 font-semibold">
                    Beta
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
                    skipFallback
                    name={open ? "chevron-down" : "chevron-right"}
                    className={`${
                      open || defaultOpen ? "" : ""
                    } text-foreground h-4 w-4`}
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
