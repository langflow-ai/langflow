import AlertDropdown from "@/alerts/alertDropDown";
import ShadTooltip from "@/components/shadTooltipComponent";
import { CustomOrgSelector } from "@/customization/components/custom-org-selector";
import { CustomProductSelector } from "@/customization/components/custom-product-selector";
import {
  ENABLE_DATASTAX_LANGFLOW,
  ENABLE_NEW_LOGO,
} from "@/customization/feature-flags";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useTheme from "@/customization/hooks/use-custom-theme";
import useAlertStore from "@/stores/alertStore";
import ForwardedIconComponent from "../genericIconComponent";
import { Button } from "../ui/button";
import { Separator } from "../ui/separator";
import ShortDataStaxLogo from "./assets/ShortDataStaxLogo.svg?react";
import ShortLangFlowIcon from "./assets/ShortLangFlowIcon.svg?react";
import { AccountMenu } from "./components/AccountMenu";
import FlowMenu from "./components/FlowMenu";
import GithubStarComponent from "./components/GithubStarButton";

export default function AppHeader(): JSX.Element {
  const notificationCenter = useAlertStore((state) => state.notificationCenter);
  const navigate = useCustomNavigate();
  useTheme();

  return (
    <div className="relative flex items-center border-b px-4 py-1.5 dark:bg-black">
      {/* Left Section */}
      <div className="flex w-full items-center gap-2 lg:max-w-[475px]">
        <Button
          unstyled
          onClick={() => navigate("/")}
          className="flex h-8 w-8 items-center"
          data-testid="icon-ChevronLeft"
        >
          {ENABLE_DATASTAX_LANGFLOW ? (
            <ShortDataStaxLogo className="fill-black dark:fill-[white]" />
          ) : ENABLE_NEW_LOGO ? (
            <ShortLangFlowIcon className="fill-black dark:fill-[white]" />
          ) : (
            <span className="fill-black text-2xl dark:fill-white">⛓️</span>
          )}
        </Button>
        {ENABLE_DATASTAX_LANGFLOW && (
          <>
            <CustomOrgSelector />
            <CustomProductSelector />
          </>
        )}
      </div>

      {/* Middle Section */}
      <div className="mx-auto flex items-center px-5">
        <FlowMenu />
      </div>

      {/* Right Section */}
      <div className="flex items-center gap-2">
        {!ENABLE_DATASTAX_LANGFLOW && (
          <>
            <Button
              unstyled
              className="flex items-center"
              onClick={() =>
                window.open("https://github.com/langflow-ai/langflow", "_blank")
              }
            >
              <GithubStarComponent />
            </Button>
            <Separator
              orientation="vertical"
              className="h-7 dark:border-zinc-700"
            />
          </>
        )}
        <AlertDropdown>
          <ShadTooltip content="Notifications" side="bottom">
            <Button variant="ghost" className="flex text-sm font-medium">
              {notificationCenter && (
                <div className="header-notifications-dot"></div>
              )}
              <ForwardedIconComponent
                name="bell"
                className="side-bar-button-size"
                aria-hidden="true"
              />
              Notifications
            </Button>
          </ShadTooltip>
        </AlertDropdown>
        {!ENABLE_DATASTAX_LANGFLOW && (
          <>
            <ShadTooltip content="Store" side="bottom">
              <Button
                variant="ghost"
                className="flex items-center text-sm font-medium"
                onClick={() => navigate("/store")}
                data-testid="button-store"
              >
                <ForwardedIconComponent
                  name="Store"
                  className="side-bar-button-size"
                />
                Store
              </Button>
            </ShadTooltip>
            <Separator
              orientation="vertical"
              className="h-7 dark:border-zinc-700"
            />
          </>
        )}
        {ENABLE_DATASTAX_LANGFLOW && (
          <>
            <ShadTooltip content="Docs" side="bottom">
              <Button
                variant="ghost"
                className="flex text-sm font-medium"
                onClick={() =>
                  window.open(
                    "https://docs.datastax.com/en/langflow/index.html",
                    "_blank",
                  )
                }
              >
                <ForwardedIconComponent
                  name="book-open-text"
                  className="side-bar-button-size"
                  aria-hidden="true"
                />
                Docs
              </Button>
            </ShadTooltip>
            <ShadTooltip content="Settings" side="bottom">
              <Button
                data-testid="user-profile-settings"
                variant="ghost"
                className="flex text-sm font-medium"
                onClick={() => navigate("/settings")}
              >
                <ForwardedIconComponent
                  name="Settings"
                  className="side-bar-button-size"
                />
                Settings
              </Button>
            </ShadTooltip>
            <Separator
              orientation="vertical"
              className="h-7 dark:border-zinc-700"
            />
          </>
        )}
        <AccountMenu />
      </div>
    </div>
  );
}
