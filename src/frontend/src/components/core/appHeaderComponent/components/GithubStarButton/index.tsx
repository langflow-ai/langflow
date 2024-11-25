import ShadTooltip from "@/components/common/shadTooltipComponent";
import { useDarkStore } from "@/stores/darkStore";
import { FaGithub } from "react-icons/fa";

export const GithubStarComponent = () => {
  const stars: number | undefined = useDarkStore((state) => state.stars);

  return (
    <ShadTooltip content="Go to Github repo" side="bottom" styleClasses="z-10">
      <div className="group inline-flex h-8 items-center justify-center gap-1 rounded-md border bg-muted px-2 pr-0 hover:border-input hover:bg-secondary-hover">
        <FaGithub className="h-4 w-4" />
        <div className="hidden text-xs font-semibold lg:block">Star</div>
        <div className="-mr-px ml-1 flex h-8 items-center justify-center rounded-md rounded-l-none border bg-background px-2 text-xs font-semibold text-secondary-foreground group-hover:border-input">
          {stars?.toLocaleString() ?? 0}
        </div>
      </div>
    </ShadTooltip>
  );
};

export default GithubStarComponent;
