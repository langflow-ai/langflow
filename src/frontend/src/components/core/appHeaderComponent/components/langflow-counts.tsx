import { FaDiscord, FaGithub } from "react-icons/fa";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { DISCORD_URL, GITHUB_URL } from "@/constants/constants";
import { Case } from "@/shared/components/caseComponent";
import { useDarkStore } from "@/stores/darkStore";
import { formatNumber } from "@/utils/utils";

export const LangflowCounts = () => {
  const stars: number | undefined = useDarkStore((state) => state.stars);
  const discordCount: number = useDarkStore((state) => state.discordCount);

  const formattedStars = formatNumber(stars);
  const formattedDiscordCount = formatNumber(discordCount);

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
          <div className="relative items-center rounded-md px-2 py-1 flex">
            <FaGithub className="h-4 w-4" />
            <Case condition={Boolean(formattedStars) && formattedStars !== "0"}>
              <span className="text-xs font-semibold pl-2">
                {formattedStars}
              </span>
            </Case>
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
          <div className="relative items-center rounded-md px-2 py-1 flex">
            <FaDiscord className="h-4 w-4" />
            <Case
              condition={
                Boolean(formattedDiscordCount) && formattedDiscordCount !== "0"
              }
            >
              <span className="text-xs font-semibold pl-2">
                {formattedDiscordCount}
              </span>
            </Case>
          </div>
        </Button>
      </ShadTooltip>
    </div>
  );
};

export default LangflowCounts;
