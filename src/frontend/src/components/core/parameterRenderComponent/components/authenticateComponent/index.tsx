import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useState } from "react";

const AuthenticateComponent = ({
  id,
  name,
  icon,
}: {
  id: string;
  name: string;
  icon?: string;
}): JSX.Element => {
  const [open, setOpen] = useState(false);
  const [isConnect, setIsConnect] = useState(false);

  const handleConnect = () => {
    setIsConnect(!isConnect);
  };

  const renderTriggerButton = () => (
    <PopoverTrigger asChild>
      <Button
        variant="primary"
        size="xs"
        className="w-full justify-between py-2 font-normal"
        onClick={handleConnect}
      >
        <span className="flex items-center gap-2 truncate">
          <ForwardedIconComponent name={icon || "GithubIcon"} />
          Github
        </span>
        <div className="flex overflow-hidden">
          {isConnect ? (
            <span className="flex items-center">
              <ForwardedIconComponent name="ChevronsUpDownIcon" />
            </span>
          ) : (
            <span className="flex items-center gap-2 truncate text-accent-amber-foreground">
              <ForwardedIconComponent name="ContactRoundKey" />
              Connect
            </span>
          )}
        </div>
      </Button>
    </PopoverTrigger>
  );

  return (
    <Popover open={open} onOpenChange={setOpen}>
      {renderTriggerButton()}
    </Popover>
  );
};

export default AuthenticateComponent;
