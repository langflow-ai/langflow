import type { TemplateCategoryProps } from "../../../../types/templates/types";
import TemplateExampleCard from "../TemplateCardComponent";

export function TemplateCategoryComponent({
  examples,
  onCardClick,
}: TemplateCategoryProps) {
  return (
    <>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 max-h-[calc(100vh-315px)] overflow-auto">
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
