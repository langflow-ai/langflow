import { convertTestName } from "@/components/common/storeCardComponent/utils/convert-test-name";
import { swatchColors } from "@/utils/styleUtils";
import { cn, getNumberFromString } from "@/utils/utils";
import IconComponent, {
  ForwardedIconComponent,
} from "../../../../components/common/genericIconComponent";
import { TemplateCardComponentProps } from "../../../../types/templates/types";

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
      className="group flex cursor-pointer gap-3 overflow-hidden rounded-md p-3 hover:bg-muted focus-visible:bg-muted"
      tabIndex={0}
      onKeyDown={handleKeyDown}
      onClick={onClick}
    >
      <div
        className={cn(
          "relative h-20 w-20 shrink-0 overflow-hidden rounded-md p-4 outline-none ring-ring",
          swatchColors[swatchIndex],
        )}
      >
        <IconComponent
          name={example.icon || "FileText"}
          className="absolute left-1/2 top-1/2 h-10 w-10 -translate-x-1/2 -translate-y-1/2 duration-300 group-hover:scale-105 group-focus-visible:scale-105"
        />
      </div>
      <div className="flex flex-1 flex-col justify-between">
        <div>
          <div className="flex w-full items-center">
            <h3
              className="line-clamp-3 font-semibold"
              data-testid={`template_${convertTestName(example.name)}`}
            >
              {example.name}
            </h3>
            <ForwardedIconComponent
              name="ArrowRight"
              className="mr-3 h-5 w-5 shrink-0 translate-x-0 opacity-0 transition-all duration-300 group-hover:translate-x-3 group-hover:opacity-100 group-focus-visible:translate-x-3 group-focus-visible:opacity-100"
            />
          </div>
          <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">
            {example.description}
          </p>
        </div>
      </div>
    </div>
  );
}
