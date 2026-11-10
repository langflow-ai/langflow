import { useEffect } from "react";
import { useDarkStore } from "@/stores/darkStore";

// GitHub stars and Discord members for the community surfaces. Fetching on
// mount keeps builds that hide those surfaces from calling GitHub or Discord.
export function useCommunityCounts() {
  const stars = useDarkStore((state) => state.stars);
  const discordCount = useDarkStore((state) => state.discordCount);
  const refreshStars = useDarkStore((state) => state.refreshStars);
  const refreshDiscordCount = useDarkStore(
    (state) => state.refreshDiscordCount,
  );

  useEffect(() => {
    refreshStars();
    refreshDiscordCount();
  }, [refreshStars, refreshDiscordCount]);

  return { stars, discordCount };
}
