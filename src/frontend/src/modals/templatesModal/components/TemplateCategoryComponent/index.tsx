import { ForwardedIconComponent } from "../../../../components/genericIconComponent";
import { TemplateCategoryProps } from "../../../../types/templates/types";
import TemplateExampleCard from "../TemplateCardComponent";

export function TemplateCategoryComponent({
  currentTab,
  examples,
  onCardClick,
}: TemplateCategoryProps) {
  return (
    <>
      <div className="flex items-center gap-3 font-medium">
        <ForwardedIconComponent
          name={currentTab?.icon ?? "Search"}
          className="h-4 w-4 text-muted-foreground"
        />
        {currentTab?.title ?? "All Templates"}
      </div>
      <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
        {examples.map((example, index) => (
          <TemplateExampleCard
            key={index}
            example={example}
            onClick={() => onCardClick(example)}
          />
        ))}
      </div>
    </>
  );
}
