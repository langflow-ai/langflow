import ForwardedIconComponent from "../../../../../../components/common/genericIconComponent";
import { Button } from "@/components/ui/button";

type ButtonVariant =
  | "default"
  | "outline"
  | "icon"
  | "ghost"
  | "link"
  | "error";

interface GeneralPageHeaderProps {
  title: string;
  subtitle?: string;
  iconName?: string;
  actionButton?: {
    label: string;
    iconName?: string;
    onClick: () => void;
    testId?: string;
    variant?: ButtonVariant;
  };
}

const GeneralPageHeaderComponent = ({
  title,
  subtitle,
  iconName,
  actionButton,
}: GeneralPageHeaderProps) => {
  return (
    <div className="flex w-full items-center justify-between gap-4">
      <div className="flex flex-col w-full">
        <h2 className="text-primary-font flex gap-2 items-center text-lg font-medium">
          {title}
          {iconName && (
            <ForwardedIconComponent
              name={iconName}
              className="h-4 w-4 text-menu"
            />
          )}
        </h2>

        {subtitle && <p className="text-sm text-secondary-font">{subtitle}</p>}
      </div>

      {actionButton && (
        <Button
          variant={actionButton.variant ?? "default"}
          onClick={actionButton.onClick}
          data-testid={actionButton.testId}
        >
          {actionButton.iconName && (
            <ForwardedIconComponent
              name={actionButton.iconName}
              className="w-4"
            />
          )}
          <span>{actionButton.label}</span>
        </Button>
      )}
    </div>
  );
};

export default GeneralPageHeaderComponent;
