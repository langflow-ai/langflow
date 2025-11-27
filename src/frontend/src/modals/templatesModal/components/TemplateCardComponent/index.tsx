import { convertTestName } from "@/components/common/storeCardComponent/utils/convert-test-name";
import { swatchColors } from "@/utils/styleUtils";
import { cn, getNumberFromString } from "@/utils/utils";
import IconComponent, {
  ForwardedIconComponent,
} from "../../../../components/common/genericIconComponent";
import type { TemplateCardComponentProps } from "../../../../types/templates/types";
import { ChatboxIcon } from "@/assets/icons/ChatboxIcon";

export default function TemplateCardComponent({
  example,
  onClick,
}: TemplateCardComponentProps) {
  const swatchIndex =
    (example.gradient && !isNaN(parseInt(example.gradient))
      ? parseInt(example.gradient)
      : getNumberFromString(example.gradient ?? example.name)) %
    swatchColors.length;

  const handleKeyDown = (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onClick();
    }
  };

  return (
    <div
      data-testid={`template-${convertTestName(example.name)}`}
      className="group grid grid-cols-[auto_1fr] gap-2 cursor-pointer rounded-lg p-3 bg-background-surface border border-accent"
      tabIndex={0}
      onKeyDown={handleKeyDown}
      onClick={onClick}
    >
      <div
        className={cn(
          "item-center flex h-6 w-6 shrink-0 items-center justify-center rounded-[4px] p-1 bg-accent",
          swatchColors[swatchIndex]
        )}
      >
        {example.icon || <ChatboxIcon className="text-secondary-font" />}
      </div>
      <div className="flex flex-1 flex-col justify-between">
        <div
          data-testid="text_card_container"
          role={convertTestName(example.name)}
        >
          <div className="flex w-full items-center">
            <h3
              className="text-menu font-medium"
              data-testid={`template_${convertTestName(example.name)}`}
            >
              {example.name}
            </h3>
            <ForwardedIconComponent
              name="ChevronRight"
              className="h-4 w-4 translate-x-0 opacity-0 transition-all duration-300 group-hover:translate-x-3 group-hover:opacity-100 group-focus-visible:translate-x-3 group-focus-visible:opacity-100"
            />
          </div>
          <p className="mt-1 line-clamp-2 text-sm text-secondary-font">
            {example.description}
          </p>
        </div>
      </div>
    </div>
  );
}
