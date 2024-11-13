import ForwardedIconComponent from "@/components/genericIconComponent";
import { useLogout } from "@/controllers/API/queries/auth";
import { CustomFeedbackDialog } from "@/customization/components/custom-feedback-dialog";
import { CustomHeaderMenuItemsTitle } from "@/customization/components/custom-header-menu-items-title";
import { CustomProfileIcon } from "@/customization/components/custom-profile-icon";
import { ENABLE_DATASTAX_LANGFLOW } from "@/customization/feature-flags";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useAuthStore from "@/stores/authStore";
import { useDarkStore } from "@/stores/darkStore";
import { useState } from "react";
import { useParams } from "react-router-dom";
import GithubStarComponent from "../GithubStarButton";
import {
  HeaderMenu,
  HeaderMenuItemButton,
  HeaderMenuItemLink,
  HeaderMenuItems,
  HeaderMenuItemsSection,
  HeaderMenuToggle,
} from "../HeaderMenu";
import { ProfileIcon } from "../ProfileIcon";
import ThemeButtons from "../ThemeButtons";

export const AccountMenu = () => {
  const [isFeedbackOpen, setIsFeedbackOpen] = useState(false);
  const { customParam: id } = useParams();
  const version = useDarkStore((state) => state.version);
  const navigate = useCustomNavigate();
  const { mutate: mutationLogout } = useLogout();

  const { isAdmin, autoLogin } = useAuthStore((state) => ({
    isAdmin: state.isAdmin,
    autoLogin: state.autoLogin,
  }));

  const handleLogout = () => {
    mutationLogout();
  };

  return (
    <>
      <HeaderMenu>
        <HeaderMenuToggle>
          <div
            className="h-7 w-7 rounded-lg focus-visible:outline-0"
            data-testid="user-profile-settings"
          >
            {ENABLE_DATASTAX_LANGFLOW ? <CustomProfileIcon /> : <ProfileIcon />}
          </div>
        </HeaderMenuToggle>
        <HeaderMenuItems position="right">
          {ENABLE_DATASTAX_LANGFLOW && (
            <HeaderMenuItemsSection>
              <CustomHeaderMenuItemsTitle />
            </HeaderMenuItemsSection>
          )}
          <HeaderMenuItemsSection>
            <div className="flex h-[46px] w-full items-center justify-between px-3">
              <div className="pl-1 text-xs text-zinc-500">
                Version {version}
              </div>
              {!ENABLE_DATASTAX_LANGFLOW && <ThemeButtons />}
            </div>
            {ENABLE_DATASTAX_LANGFLOW ? (
              <HeaderMenuItemLink newPage href={`/settings/org/${id}/overview`}>
                Account Settings
              </HeaderMenuItemLink>
            ) : (
              <HeaderMenuItemButton
                icon="arrow-right"
                onClick={() => {
                  navigate("/settings");
                }}
              >
                Settings
              </HeaderMenuItemButton>
            )}
            {!ENABLE_DATASTAX_LANGFLOW && (
              <>
                {isAdmin && !autoLogin && (
                  <HeaderMenuItemButton onClick={() => navigate("/admin")}>
                    Admin Page
                  </HeaderMenuItemButton>
                )}
              </>
            )}
            {ENABLE_DATASTAX_LANGFLOW ? (
              <HeaderMenuItemButton onClick={() => setIsFeedbackOpen(true)}>
                Feedback
              </HeaderMenuItemButton>
            ) : (
              <HeaderMenuItemLink newPage href="https://docs.langflow.org">
                Docs
              </HeaderMenuItemLink>
            )}
          </HeaderMenuItemsSection>
          <HeaderMenuItemsSection>
            {ENABLE_DATASTAX_LANGFLOW ? (
              <HeaderMenuItemLink
                newPage
                href="https://github.com/langflow-ai/langflow"
              >
                <div className="-my-2 mr-2 flex w-full items-center justify-between">
                  <div className="text-sm">Star the repo</div>
                  <GithubStarComponent />
                </div>
              </HeaderMenuItemLink>
            ) : (
              <HeaderMenuItemLink
                newPage
                href="https://github.com/langflow-ai/langflow/discussions"
              >
                Share Feedback on Github
              </HeaderMenuItemLink>
            )}
            <HeaderMenuItemLink newPage href="https://twitter.com/langflow_ai">
              Follow Langflow on X
            </HeaderMenuItemLink>
            <HeaderMenuItemLink newPage href="https://discord.gg/EqksyE2EX9">
              Join the Langflow Discord
            </HeaderMenuItemLink>
          </HeaderMenuItemsSection>
          {ENABLE_DATASTAX_LANGFLOW ? (
            <HeaderMenuItemsSection>
              <HeaderMenuItemLink href="/session/logout" icon="log-out">
                Logout
              </HeaderMenuItemLink>
            </HeaderMenuItemsSection>
          ) : (
            !autoLogin && (
              <HeaderMenuItemsSection>
                <HeaderMenuItemButton onClick={handleLogout} icon="log-out">
                  Logout
                </HeaderMenuItemButton>
              </HeaderMenuItemsSection>
            )
          )}
        </HeaderMenuItems>
      </HeaderMenu>
      <CustomFeedbackDialog
        isOpen={isFeedbackOpen}
        setIsOpen={setIsFeedbackOpen}
      />
    </>
  );
};
