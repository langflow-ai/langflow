import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import ListSelectionComponent from "@/CustomNodes/GenericNode/components/ListSelectionComponent";
import { useState } from "react";

type ButtonComponentProps = {
  tooltip?: string;
};

const ButtonComponent = ({ tooltip = "" }: ButtonComponentProps) => {
  const [open, setOpen] = useState(false);

  return (
    <>
      <ShadTooltip content={!(tooltip as string) ? "" : tooltip}>
        <Button
          variant="default"
          size="xs"
          onClick={() => setOpen(true)}
          className="w-full py-2"
        >
          <div className="flex items-center text-sm font-semibold">
            Select action
          </div>
        </Button>
      </ShadTooltip>
      <ListSelectionComponent open={open} onClose={() => setOpen(false)} />
    </>
  );
};

export default ButtonComponent;
