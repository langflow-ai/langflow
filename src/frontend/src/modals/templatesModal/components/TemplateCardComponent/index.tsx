import { convertTestName } from "@/components/storeCardComponent/utils/convert-test-name";
import { BG_NOISE } from "@/utils/styleUtils";
import gradient from "random-gradient";
import IconComponent, {
  ForwardedIconComponent,
} from "../../../../components/genericIconComponent";
import { TemplateCardComponentProps } from "../../../../types/templates/types";

export default function TemplateCardComponent({
  example,
  onClick,
}: TemplateCardComponentProps) {
  const gradientDirections = ["horizontal", "vertical", "diagonal"];
  const directionIndex =
    (example.gradient ? example.gradient.length : example.name.length) %
    gradientDirections.length;
  const bgGradient = {
    background: gradient(
      example.gradient || example.name,
      gradientDirections[directionIndex],
    ),
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onClick();
    }
  };

  return (
    <div
      className="group flex cursor-pointer flex-col gap-4 overflow-hidden"
      tabIndex={1}
      onKeyDown={handleKeyDown}
      onClick={onClick}
    >
      <div
        className="relative h-40 overflow-hidden rounded-xl p-4 outline-none ring-ring brightness-[90%] contrast-125 saturate-[80%] group-focus-visible:border group-focus-visible:border-ring"
        style={{
          backgroundImage: BG_NOISE + "," + bgGradient.background,
          transform: "scale(1)",
          transition: "transform 0.3s ease-in-out",
        }}
      >
        <div
          className="absolute inset-0 transition-transform duration-300 group-hover:scale-110 group-focus-visible:scale-110"
          style={{
            backgroundImage: BG_NOISE + "," + bgGradient.background,
          }}
        />
        <IconComponent
          name={example.icon || "FileText"}
          className="absolute left-1/2 top-1/2 h-10 w-10 -translate-x-1/2 -translate-y-1/2 !stroke-1 text-white opacity-25 mix-blend-plus-lighter duration-300 group-hover:scale-105 group-hover:opacity-50 group-focus-visible:scale-105 group-focus-visible:opacity-50"
        />
      </div>
      <div className="flex flex-1 flex-col justify-between">
        <div>
          <div className="flex w-full items-center justify-between">
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
          <p className="mt-2 line-clamp-2 text-xs text-muted-foreground">
            {example.description}
          </p>
        </div>
      </div>
    </div>
  );
}
