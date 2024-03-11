import AccordionComponent from "../../../../components/AccordionComponent";
import { DisclosureComponentType } from "../../../../types/components";

export default function DisclosureComponent({
  button: { title, Icon, buttons = [] },
  children,
  openDisc,
}: DisclosureComponentType): JSX.Element {
  return (
    <>
      <AccordionComponent
        trigger={
          <>
            <div className="flex gap-4">
              {/* BUG ON THIS ICON */}
              <Icon strokeWidth={1.5} size={22} className="text-primary" />
              <span className="components-disclosure-title">{title}</span>
            </div>
            <div className="components-disclosure-div">
              {buttons.map((btn, index) => (
                <button key={index} onClick={btn.onClick}>
                  {btn.Icon}
                </button>
              ))}
              <div></div>
            </div>
          </>
        }
      >
        <div className="">{children}</div>
      </AccordionComponent>
    </>
  );
}
