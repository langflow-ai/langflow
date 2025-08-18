import { customOpenNewTab } from "@/customization/utils/custom-open-new-tab";
import { classNames } from "../../../../../utils/utils";
import IconComponent from "../../../../common/genericIconComponent";
import { Button } from "../../../../ui/button";
import type { InputProps, LinkComponentType } from "../../types";

const DEFAULT_ICON = "ExternalLink";

export default function LinkComponent({
  value,
  disabled = false,
  id = "",
  text,
  icon,
}: InputProps<string, LinkComponentType>): JSX.Element {
  function handleOpenLink() {
    if (value) {
      const url = !/^https?:\/\//i.test(value) ? `https://${value}` : value;
      customOpenNewTab(url);
    }
  }

  const buttonClassName = classNames(
    "nopan w-full shrink-0",
    disabled ? "cursor-not-allowed text-ring" : "hover:text-accent-foreground",
  );

  const ButtonContent = ({ icon, text }: { icon: string; text: string }) => {
    return (
      <div className="flex items-center gap-2">
        <IconComponent
          name={icon ?? DEFAULT_ICON}
          className="h-5 w-5"
          aria-hidden="true"
        />
        {text && <span>{text}</span>}
      </div>
    );
  };

  return (
    <div className="flex w-full items-center gap-3">
      <Button
        data-testid={id}
        onClick={handleOpenLink}
        disabled={disabled || !value}
        type="button"
        variant="primary"
        size="sm"
        className={buttonClassName}
      >
        <ButtonContent icon={icon ?? DEFAULT_ICON} text={text ?? ""} />
      </Button>
    </div>
  );
}
