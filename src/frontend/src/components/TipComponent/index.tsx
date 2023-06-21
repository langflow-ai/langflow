import { Info, HelpCircle } from "lucide-react";
import { TipType } from "../../types/components";
import ShadTooltip from "../ShadTooltipComponent";


export default function TipComponent({ delayDuration = 1000, content, side }: TipType) {
  return (
    <div className="items-center text-center">
    <ShadTooltip
            delayDuration={delayDuration}
            content={content}
            side={side}
          > 
      <HelpCircle size={17} color={"#1d4ed8"} />

    </ShadTooltip>
  </div>
  );
};
