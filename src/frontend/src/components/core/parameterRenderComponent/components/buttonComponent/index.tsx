import DialogComponent from "@/components/common/dialogComponent";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useState } from "react";

const ButtonComponent = ({
  id,
  name,
  icon,
}: {
  id: string;
  name: string;
  icon?: string;
}): JSX.Element => {
  const [open, setOpen] = useState(false);

  const renderPopoverContent = () => (
    <DialogComponent open={open} onOpenChange={setOpen} />
  );

  return (
    <>
      <Button
        variant="default"
        size="xs"
        className="w-full py-2 font-normal font-semibold"
        onClick={() => setOpen(true)}
      >
        Actions
      </Button>
      {open && renderPopoverContent()}
    </>
  );
};

export default ButtonComponent;
