import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import {
  DATASTAX_DOCS_URL,
  DISCORD_URL,
  DOCS_URL,
  GITHUB_URL,
  TWITTER_URL,
} from "@/constants/constants";
import { useLogout } from "@/controllers/API/queries/auth";
import { ENABLE_DATASTAX_LANGFLOW } from "@/customization/feature-flags";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useAuthStore from "@/stores/authStore";
import { useDarkStore } from "@/stores/darkStore";
import { cn } from "@/utils/utils";
import { FaDiscord, FaGithub, FaTwitter } from "react-icons/fa";
import { useParams } from "react-router-dom";
import {
  HeaderMenu,
  HeaderMenuItemButton,
  HeaderMenuItemLink,
  HeaderMenuItems,
  HeaderMenuToggle,
} from "../HeaderMenu";
import { ProfileIcon } from "../ProfileIcon";
import ThemeButtons from "../ThemeButtons";

export const AccountMenu = () => {
  const { customParam: id } = useParams();
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

  const isLatestVersion = version === latestVersion;

  return (
    <>
      <HeaderMenu>
        <HeaderMenuToggle>
          <div
            className="group h-9 w-9 overflow-hidden rounded-full ring-2 ring-border/50 transition-all duration-300 hover:ring-4 hover:ring-border focus-visible:outline-0 active:scale-95"
            data-testid="user-profile-settings"
          >
            <div className="transition-transform duration-300 group-hover:scale-110">
              <ProfileIcon />
            </div>
          </div>
        </HeaderMenuToggle>
        <HeaderMenuItems position="right" classNameSize="w-[320px]">
          <div className="divide-y divide-border/10 overflow-hidden rounded-xl bg-background/80 shadow-lg backdrop-blur-sm">
            {/* <div className="px-4 py-3">
              <div className="flex items-center justify-between">
                <span
                  data-testid="menu_version_button"
                  id="menu_version_button"
                  className="text-sm font-medium text-muted-foreground"
                >
                  Version
                </span>
                <div
                  className={cn(
                    "flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium shadow-sm transition-all duration-300",
                    isLatestVersion 
                      ? "bg-emerald-500/10 text-emerald-500 ring-1 ring-emerald-500/20" 
                      : "animate-pulse bg-amber-500/10 text-amber-500 ring-1 ring-amber-500/20"
                  )}
                >
                  <div className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    isLatestVersion ? "bg-emerald-500" : "bg-amber-500"
                  )} />
                  {version}
                  <span className="opacity-60">
                    {isLatestVersion ? "(latest)" : "(update available)"}
                  </span>
                </div>
              </div>
            </div> */}

            <div className="space-y-1 p-1.5">
              {/* <HeaderMenuItemButton
                onClick={() => navigate("/settings")}
                icon="Settings"
              >
                <div className="flex items-center gap-3 px-2">
                  <div className="rounded-md bg-muted p-1.5">
                    <ForwardedIconComponent name="Settings" className="h-4 w-4 text-foreground/70" />
                  </div>
                  <span className="font-medium">Settings</span>
                </div>
              </HeaderMenuItemButton> */}

              {isAdmin && !autoLogin && (
                <HeaderMenuItemButton
                  onClick={() => navigate("/admin")}
                  icon="Shield"
                >
                  <div className="flex items-center gap-3 px-2">
                    <div className="rounded-md bg-muted p-1.5">
                      <ForwardedIconComponent name="Shield" className="h-4 w-4 text-foreground/70" />
                    </div>
                    <span className="font-medium">Admin Page</span>
                  </div>
                </HeaderMenuItemButton>
              )}
            </div>

            {/* <div className="p-3">
              <div className="flex items-center justify-between rounded-lg bg-muted/50 px-4 py-2.5">
                <span className="text-sm font-medium text-muted-foreground">Theme</span>
                <div className="relative">
                  <ThemeButtons />
                </div>
              </div>
            </div> */}

            {!autoLogin && (
              <div className="p-1.5">
                <HeaderMenuItemButton onClick={handleLogout} icon="log-out">
                  <div className="flex items-center gap-3 px-2">
                    <div className="rounded-md bg-destructive/10 p-1.5">
                      <ForwardedIconComponent name="LogOut" className="h-4 w-4 text-destructive" />
                    </div>
                    <span className="font-medium text-destructive">Logout</span>
                  </div>
                </HeaderMenuItemButton>
              </div>
            )}
          </div>
        </HeaderMenuItems>
      </HeaderMenu>
    </>
  );
};
