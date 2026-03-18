import { FaDiscord, FaGithub } from "react-icons/fa";
import { useTranslation } from "react-i18next";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import {
  DATASTAX_DOCS_URL,
  DISCORD_URL,
  DOCS_URL,
  GITHUB_URL,
  TWITTER_URL,
} from "@/constants/constants";
import { useLogout } from "@/controllers/API/queries/auth";
import { CustomProfileIcon } from "@/customization/components/custom-profile-icon";
import { ENABLE_DATASTAX_LANGFLOW } from "@/customization/feature-flags";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useAuthStore from "@/stores/authStore";
import { useDarkStore } from "@/stores/darkStore";
import { cn, stripReleaseStageFromVersion } from "@/utils/utils";
import {
  HeaderMenu,
  HeaderMenuItemButton,
  HeaderMenuItemLink,
  HeaderMenuItems,
  HeaderMenuToggle,
} from "../HeaderMenu";
import ThemeButtons from "../ThemeButtons";

export const AccountMenu = () => {
  const { t } = useTranslation();
  const version = useDarkStore((state) => state.version);
  const latestVersion = useDarkStore((state) => state.latestVersion);
  const navigate = useCustomNavigate();
  const { mutate: mutationLogout } = useLogout();

  const { isAdmin, autoLogin } = useAuthStore((state) => ({
    isAdmin: state.isAdmin,
    autoLogin: state.autoLogin,
  }));

  const handleLogout = () => {
    mutationLogout();
  };

  const isLatestVersion = (() => {
    if (!version || !latestVersion) return false;

    const currentBaseVersion = stripReleaseStageFromVersion(version);
    const latestBaseVersion = stripReleaseStageFromVersion(latestVersion);

    return currentBaseVersion === latestBaseVersion;
  })();

  return (
    <HeaderMenu>
      <HeaderMenuToggle>
        <div
          className="h-6 w-6 rounded-lg focus-visible:outline-0"
          data-testid="user-profile-settings"
        >
          <CustomProfileIcon />
        </div>
      </HeaderMenuToggle>
      <HeaderMenuItems position="right" classNameSize="w-[272px]">
        <div className="divide-y divide-foreground/10">
          <div>
            <div className="h-[44px] items-center px-4 pt-3">
              <div className="flex items-center justify-between">
                <span
                  data-testid="menu_version_button"
                  id="menu_version_button"
                  className="text-sm"
                >
                  {t("account.version")}
                </span>
                <div
                  className={cn(
                    "float-right text-xs",
                    isLatestVersion && "text-accent-emerald-foreground",
                    !isLatestVersion && "text-accent-amber-foreground",
                  )}
                >
                  {version}{" "}
                  {isLatestVersion ? t("account.latest") : t("account.updateAvailable")}
                </div>
              </div>
            </div>
          </div>

          <div>
            <HeaderMenuItemButton
              onClick={() => {
                navigate("/settings");
              }}
            >
              <span
                data-testid="menu_settings_button"
                id="menu_settings_button"
              >
                {t("account.settings")}
              </span>
            </HeaderMenuItemButton>

            {isAdmin && !autoLogin && (
              <div>
                <HeaderMenuItemButton
                  onClick={() => {
                    navigate("/admin");
                  }}
                >
                  <span
                    data-testid="menu_admin_page_button"
                    id="menu_admin_page_button"
                  >
                    {t("account.adminPage")}
                  </span>
                </HeaderMenuItemButton>
              </div>
            )}
            <HeaderMenuItemLink
              newPage
              href={ENABLE_DATASTAX_LANGFLOW ? DATASTAX_DOCS_URL : DOCS_URL}
            >
              <span data-testid="menu_docs_button" id="menu_docs_button">
                {t("account.docs")}
              </span>
            </HeaderMenuItemLink>
          </div>

          <div>
            <HeaderMenuItemLink newPage href={GITHUB_URL}>
              <span
                data-testid="menu_github_button"
                id="menu_github_button"
                className="flex items-center gap-2"
              >
                <FaGithub className="h-4 w-4" />
                {t("account.github")}
              </span>
            </HeaderMenuItemLink>
            <HeaderMenuItemLink newPage href={DISCORD_URL}>
              <span
                data-testid="menu_discord_button"
                id="menu_discord_button"
                className="flex items-center gap-2"
              >
                <FaDiscord className="h-4 w-4 text-[#5865F2]" />
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

          <div className="flex items-center justify-between px-4 py-[6.5px] text-sm">
            <span className="">{t("account.theme")}</span>
            <div className="relative top-[1px] float-right">
              <ThemeButtons />
            </div>
          </div>

          {!autoLogin && (
            <div>
              <HeaderMenuItemButton onClick={handleLogout} icon="log-out">
                {t("account.logout")}
              </HeaderMenuItemButton>
            </div>
          )}
        </div>
      </HeaderMenuItems>
    </HeaderMenu>
  );
};
