import { useTranslation } from "react-i18next";
import { FaDiscord, FaGithub } from "react-icons/fa";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { DISCORD_URL, GITHUB_URL, TWITTER_URL } from "@/constants/constants";
import { HeaderMenuItemLink } from "../HeaderMenu";

/** Account menu group linking to the Langflow GitHub, Discord and X pages. */
export const AccountMenuCommunityLinks = () => {
  const { t } = useTranslation();

  return (
    <div>
      <HeaderMenuItemLink newPage href={GITHUB_URL}>
        <span
          data-testid="menu_github_button"
          id="menu_github_button"
          className="flex items-center gap-2"
        >
          <FaGithub className="h-4 w-4" aria-hidden="true" />
          {t("account.github")}
        </span>
      </HeaderMenuItemLink>
      <HeaderMenuItemLink newPage href={DISCORD_URL}>
        <span
          data-testid="menu_discord_button"
          id="menu_discord_button"
          className="flex items-center gap-2"
        >
          <FaDiscord className="h-4 w-4 text-[#5865F2]" aria-hidden="true" />
          {t("account.discord")}
        </span>
      </HeaderMenuItemLink>
      <HeaderMenuItemLink newPage href={TWITTER_URL}>
        <span
          data-testid="menu_twitter_button"
          id="menu_twitter_button"
          className="flex items-center gap-2"
        >
          <ForwardedIconComponent
            strokeWidth={2}
            name="TwitterX"
            className="h-4 w-4"
          />
          {t("account.twitter")}
        </span>
      </HeaderMenuItemLink>
    </div>
  );
};
