import { Disclosure } from "@headlessui/react";
import IconComponent from "../../../../components/common/genericIconComponent";
import { DisclosureComponentType } from "../../../../types/components";

export default function DisclosureComponent({
  button: { title, icon, buttons = [] },
  isChild = true,
  children,
  defaultOpen,
}: DisclosureComponentType): JSX.Element {
  return (
    <Disclosure as="div" defaultOpen={defaultOpen} key={title}>
      {({ open }) => (
        <>
          <div>
            <Disclosure.Button
              className={
                isChild
                  ? "components-disclosure-arrangement-child"
                  : "components-disclosure-arrangement"
              }
              data-testid={`disclosure-${title.toLocaleLowerCase()}`}
            >
              <div className={"flex gap-4" + (isChild ? " pl-2" : "")}>
                {/* BUG ON THIS ICON */}
                <IconComponent name={icon} />
                <span className="components-disclosure-title">{title}</span>
              </div>
              <div className="components-disclosure-div">
                {buttons.map((btn, index) => (
                  <button key={index} onClick={btn.onClick}>
                    <IconComponent name={btn.icon} />
                  </button>
                ))}
                <div>
                  <IconComponent
                    name="ChevronRight"
                    className={`${
                      open || defaultOpen ? "rotate-90 transform" : ""
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
