import AppHeader from "@/components/appHeaderComponent";
import useTheme from "@/customization/hooks/use-custom-theme";
import { Outlet } from "react-router-dom";

export function DashboardWrapperPage() {
  useTheme();

  return (
    <div className="flex h-screen w-full flex-col">
      <AppHeader />
      <div className="flex h-full w-full flex-row">
        <Outlet />
      </div>
    </div>
  );
}
