import type { TemplateCategoryProps } from "../../../../types/templates/types";
import TemplateExampleCard from "../TemplateCardComponent";

interface TemplateCategoryComponentProps extends TemplateCategoryProps {
  loading: boolean;
  onDelete?: (example: TemplateCategoryProps["examples"][number]) => void;
  canDelete?: (example: TemplateCategoryProps["examples"][number]) => boolean;
}

export function TemplateCategoryComponent({
  examples,
  onCardClick,
  onDelete,
  canDelete,
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
            onDelete={
              onDelete && canDelete?.(example)
                ? () => onDelete(example)
                : undefined
            }
            disabled={loading}
          />
        ))}
      </div>
    </>
  );
}
