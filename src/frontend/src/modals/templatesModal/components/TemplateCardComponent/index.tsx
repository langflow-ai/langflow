import { convertTestName } from "@/components/storeCardComponent/utils/convert-test-name";
import { BG_NOISE, flowGradients } from "@/utils/styleUtils";
import IconComponent, {
  ForwardedIconComponent,
} from "../../../../components/genericIconComponent";
import { TemplateCardComponentProps } from "../../../../types/templates/types";

export default function TemplateCardComponent({
  example,
  onClick,
}: TemplateCardComponentProps) {
  const directionIndex =
    (example.gradient && example.gradient.split(",").length == 1
      ? example.gradient.length
      : example.name.length) % flowGradients.length;

  const handleKeyDown = (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onClick();
    }
  };

  const bgGradient =
    BG_NOISE +
    "," +
    (example.gradient && example.gradient.split(",").length > 1
      ? "linear-gradient(90deg, " + example.gradient + ")"
      : flowGradients[directionIndex]);

  return (
    <div
      className="group flex cursor-pointer gap-3 overflow-hidden rounded-md p-3 hover:bg-muted focus-visible:bg-muted"
      tabIndex={0}
      onKeyDown={handleKeyDown}
      onClick={onClick}
    >
      <div className="relative h-20 w-20 shrink-0 overflow-hidden rounded-md bg-muted p-4 outline-none ring-ring group-hover:bg-border group-focus-visible:bg-border">
        <IconComponent
          name={example.icon || "FileText"}
          className="absolute left-1/2 top-1/2 h-10 w-10 -translate-x-1/2 -translate-y-1/2 text-muted-foreground duration-300 group-hover:scale-105 group-hover:text-foreground group-focus-visible:scale-105 group-focus-visible:text-foreground"
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
