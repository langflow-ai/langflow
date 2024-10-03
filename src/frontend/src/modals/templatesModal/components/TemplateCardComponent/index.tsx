import IconComponent, {
  ForwardedIconComponent,
} from "../../../../components/genericIconComponent";
import { TemplateCardComponentProps } from "../../../../types/templates/types";

export default function TemplateCardComponent({
  example,
  onClick,
}: TemplateCardComponentProps) {
  return (
    <div
      className="group flex cursor-pointer flex-col gap-4 overflow-hidden"
      onClick={onClick}
    >
      <div className="relative h-40 rounded-xl bg-gradient-to-br from-primary/20 to-secondary/20 p-4">
        <IconComponent
          name={example.icon || "FileText"}
          className="absolute left-1/2 top-1/2 h-10 w-10 -translate-x-1/2 -translate-y-1/2 stroke-1 text-primary opacity-50 duration-300 group-hover:scale-105 group-hover:opacity-100"
        />
      </div>
      <div className="flex flex-1 flex-col justify-between">
        <div>
          <div className="flex w-full items-center justify-between">
            <h3 className="line-clamp-3 text-lg font-semibold">
              {example.name}
            </h3>
            <ForwardedIconComponent
              name="ArrowRight"
              className="mr-3 h-5 w-5 shrink-0 translate-x-0 opacity-0 transition-all duration-300 group-hover:translate-x-3 group-hover:opacity-100"
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
