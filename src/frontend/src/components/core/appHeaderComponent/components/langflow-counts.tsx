import ShadTooltip from "@/components/common/shadTooltipComponent";
import { useDarkStore } from "@/stores/darkStore";
import { formatNumber } from "@/utils/utils";
import { FaDiscord, FaGithub } from "react-icons/fa";

export const LangflowCounts = () => {
  const stars: number | undefined = useDarkStore((state) => state.stars);
  const discordCount: number = useDarkStore((state) => state.discordCount);

  return (
    <div className="flex items-center gap-3">
      <ShadTooltip
        content="Go to GitHub repo"
        side="bottom"
        styleClasses="z-10"
      >
        <div className="hit-area-hover flex items-center gap-2 rounded-md p-1 text-muted-foreground">
          <FaGithub className="h-4 w-4" />
          <span className="text-xs font-semibold">{formatNumber(stars)}</span>
        </div>
      </ShadTooltip>

      <ShadTooltip
        content="Go to Discord server"
        side="bottom"
        styleClasses="z-10"
      >
        <div className="hit-area-hover flex items-center gap-2 rounded-md p-1 text-muted-foreground">
          <FaDiscord className="h-4 w-4" />
          <span className="text-xs font-semibold">
            {formatNumber(discordCount)}
          </span>
        </div>
      </ShadTooltip>
    </div>
  );
};

export default LangflowCounts;
