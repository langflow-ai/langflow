import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/utils";
import { InputProps } from "../../types";

type ButtonComponentType = {
  value: string;
  isAuth?: boolean;
};

const ButtonComponent = ({
  value,
  isAuth = true,
  ...baseInputProps
}: InputProps<string, ButtonComponentType>) => {
  const { tooltip } = baseInputProps;
  const icon = "github";

  const handleClick = () => {
    console.log("clicked");
  };

  return (
    <ShadTooltip content={!value ? (tooltip as string) : ""}>
      <Button
        variant="default"
        size="xs"
        onClick={handleClick}
        className="w-full py-2"
      >
        <div className="flex w-full items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            {icon && <ForwardedIconComponent name={icon} className="h-4 w-4" />}
            {value}
          </div>
          {isAuth && (
            <div className="accent-amber-foreground flex items-center gap-2">
              <ForwardedIconComponent name="lock" />
              <span className="accent-amber-foreground text-base--medium">
                Connect
              </span>
            </div>
          )}
        </div>
      </Button>
    </ShadTooltip>
  );
};

export default ButtonComponent;
