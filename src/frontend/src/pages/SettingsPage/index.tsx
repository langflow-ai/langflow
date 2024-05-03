import { useEffect } from "react";
import { Outlet } from "react-router-dom";
import ForwardedIconComponent from "../../components/genericIconComponent";
import PageLayout from "../../components/pageLayout";
import SidebarNav from "../../components/sidebarComponent";
import useFlowsManagerStore from "../../stores/flowsManagerStore";

export default function SettingsPage(): JSX.Element {
  const pathname = location.pathname;
  const setCurrentFlowId = useFlowsManagerStore(
    (state) => state.setCurrentFlowId
  );
  useEffect(() => {
    setCurrentFlowId("");
  }, [pathname]);

  const sidebarNavItems = [
    {
      title: "General",
      href: "/settings/general",
      icon: (
        <ForwardedIconComponent
          name="SlidersHorizontal"
          className="mx-[0.08rem] w-[1.1rem] stroke-[1.5]"
        />
      ),
    },
    /* {
        title: "Theme",
        href: "/settings/theme",
        icon: (
          <ForwardedIconComponent
            name="Palette"
            className="mx-[0.08rem] w-[1.1rem] stroke-[1.5]"
          />
        ),
      },
      {
        title: "Bundles",
        href: "/settings/bundles",
        icon: (
          <ForwardedIconComponent
            name="Boxes"
            className="mx-[0.08rem] w-[1.1rem] stroke-[1.5]"
          />
        ),
      },
      {
        title: "Integrations",
        href: "/settings/integrations",
        icon: (
          <ForwardedIconComponent
            name="Blocks"
            className="mx-[0.08rem] w-[1.1rem] stroke-[1.5]"
          />
        ),
      }, */
    {
      title: "Global Variables",
      href: "/settings/global-variables",
      icon: (
        <ForwardedIconComponent
          name="Globe"
          className="mx-[0.08rem] w-[1.1rem] stroke-[1.5]"
        />
      ),
    },
    {
      title: "Shortcuts",
      href: "/settings/shortcuts",
      icon: (
        <ForwardedIconComponent name="Keyboard" className="w-5 stroke-[1.5]" />
      ),
    },
  ];
  return (
    <PageLayout
      title="Settings"
      description="Manage the general settings for Langflow."
    >
      <div className="flex h-full w-full space-y-8 lg:flex-row lg:space-x-8 lg:space-y-0">
        <aside className="flex h-full flex-col space-y-6 lg:w-1/5">
          <SidebarNav items={sidebarNavItems} />
        </aside>
        <div className="h-full w-full flex-1">
          <Outlet />
        </div>
      </div>
    </PageLayout>
  );
}
