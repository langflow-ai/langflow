import { LinkComponentType } from "@/types/components";
import { useCallback, useEffect, useState } from "react";
import { classNames } from "../../utils/utils";
import IconComponent from "../genericIconComponent";
import { Button } from "../ui/button";

const DEFAULT_ICON = "ExternalLink";

export default function LinkComponent({
  value,
  disabled = false,
  id = "",
}: LinkComponentType): JSX.Element {
  const [componentValue, setComponentValue] = useState(value);

  useEffect(() => {
    setComponentValue(value);
  }, [value]);

  const handleOpenLink = useCallback(() => {
    if (componentValue?.value) {
      const url = !/^https?:\/\//i.test(componentValue.value)
        ? `https://${componentValue.value}`
        : componentValue.value;
      window.open(url, "_blank", "noopener,noreferrer");
    }
  }, [componentValue]);

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
        disabled={disabled || !componentValue}
        type="button"
        variant="primary"
        size="sm"
        className={buttonClassName}
      >
        <ButtonContent
          icon={componentValue?.icon ?? DEFAULT_ICON}
          text={componentValue?.text ?? ""}
        />
      </Button>
    </div>
  );
}
