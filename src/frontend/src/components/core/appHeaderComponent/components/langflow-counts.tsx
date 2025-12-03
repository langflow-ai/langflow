import { FaDiscord, FaGithub } from "react-icons/fa";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { DISCORD_URL, GITHUB_URL } from "@/constants/constants";
import { useDarkStore } from "@/stores/darkStore";
import { formatNumber } from "@/utils/utils";

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
        <Button
          unstyled
          onClick={() => window.open(GITHUB_URL, "_blank")}
          className="hit-area-hover flex items-center gap-2 rounded-md p-1 text-muted-foreground"
        >
          <div className="hit-area-hover group relative items-center rounded-md px-2 py-1 text-muted-foreground flex">
            <FaGithub className="h-4 w-4" />
            <span className="text-xs font-semibold pl-2">
              {formatNumber(stars)}
            </span>
          </div>
        </Button>
      </ShadTooltip>

      <ShadTooltip
        content="Go to Discord server"
        side="bottom"
        styleClasses="z-10"
      >
        <Button
          unstyled
          onClick={() => window.open(DISCORD_URL, "_blank")}
          className="hit-area-hover flex items-center gap-2 rounded-md p-1 text-muted-foreground"
        >
          <div className="hit-area-hover group relative items-center rounded-md px-2 py-1 text-muted-foreground flex">
            <FaDiscord className="h-4 w-4" />
            <span className="text-xs font-semibold pl-2">
              {formatNumber(discordCount)}
            </span>
          </div>
        </Button>
      </ShadTooltip>
    </div>
  );
};

export default LangflowCounts;
