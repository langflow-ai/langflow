import type { TemplateCategoryProps } from "../../../../types/templates/types";
import TemplateExampleCard from "../TemplateCardComponent";

interface TemplateCategoryComponentProps extends TemplateCategoryProps {
  loading: boolean;
}

export function TemplateCategoryComponent({
  examples,
  onCardClick,
  loading,
}: TemplateCategoryComponentProps) {
  return (
    <>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {examples.map((example, index) => (
          <TemplateExampleCard
            key={index}
            example={example}
            onClick={() => onCardClick(example)}
            disabled={loading}
          />
        ))}
      </div>
    </>
  );
}
