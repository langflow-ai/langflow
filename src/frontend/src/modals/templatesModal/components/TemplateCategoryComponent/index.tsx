import { TemplateCategoryProps } from "../../../../types/templates/types";
import TemplateExampleCard from "../TemplateCardComponent";

export function TemplateCategoryComponent({
  currentTab,
  examples,
  onCardClick,
}: TemplateCategoryProps) {
  return (
    <>
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
