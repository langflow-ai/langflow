import ShadTooltip from "@/components/common/shadTooltipComponent";
import { useDarkStore } from "@/stores/darkStore";
import { formatNumber } from "@/utils/utils";
import { FaDiscord, FaGithub } from "react-icons/fa";

export const LangflowCounts = () => {
  const stars: number | undefined = useDarkStore((state) => state.stars);
  const discordCount: number = useDarkStore((state) => state.discordCount);

  return (
    <div className="flex items-center gap-4">
      <ShadTooltip
        content="Go to Github repo"
        side="bottom"
        styleClasses="z-10"
      >
        <div className="flex items-center gap-1">
          <FaGithub className="h-4 w-4" />
          <span className="text-xs font-semibold text-muted-foreground">
            {formatNumber(stars)}
          </span>
        </div>
      </ShadTooltip>

      <ShadTooltip
        content="Go to Github repo"
        side="bottom"
        styleClasses="z-10"
      >
        <div className="flex items-center gap-1">
          <FaDiscord className="h-4 w-4 text-[#5865F2]" />
          <span className="text-xs font-semibold text-muted-foreground">
            {formatNumber(discordCount)}
          </span>
        </div>
      </ShadTooltip>
    </div>
  );
};

export default LangflowCounts;
