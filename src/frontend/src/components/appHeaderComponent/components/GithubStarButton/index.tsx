import { useDarkStore } from "@/stores/darkStore";
import { FaGithub } from "react-icons/fa";

export const GithubStarComponent = () => {
  const stars = useDarkStore((state) => state.stars);

  return (
    <div className="header-github-link gap-1 bg-zinc-100 dark:bg-zinc-900 dark:hover:bg-zinc-900">
      <FaGithub className="h-4 w-4 text-black dark:text-[white]" />
      <div className="hidden text-black dark:text-[white] lg:block">Star</div>
      <div className="header-github-display text-black dark:text-[white]">
        {stars.toLocaleString() ?? 0}
      </div>
    </div>
  );
};

export default GithubStarComponent;
