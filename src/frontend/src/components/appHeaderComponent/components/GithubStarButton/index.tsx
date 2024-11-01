import ShadTooltip from "@/components/shadTooltipComponent";
import { useDarkStore } from "@/stores/darkStore";
import { FaGithub } from "react-icons/fa";

export const GithubStarComponent = () => {
  const stars = useDarkStore((state) => state.stars);

  return (
    <ShadTooltip content="Go to Github repo" side="bottom" styleClasses="z-10">
      <div className="header-github-link-box gap-1 bg-muted hover:bg-zinc-200 dark:bg-zinc-900 dark:hover:bg-zinc-800">
        <FaGithub className="h-4 w-4 text-black dark:text-[white]" />
        <div className="hidden text-xs font-semibold text-black dark:text-[white] lg:block">
          Star
        </div>
        <div className="header-github-display text-xs font-semibold text-black dark:text-[white]">
          {stars.toLocaleString() ?? 0}
        </div>
      </div>
    </ShadTooltip>
  );
};

export default GithubStarComponent;
