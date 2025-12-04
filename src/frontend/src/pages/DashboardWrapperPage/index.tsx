import { Outlet } from "react-router-dom";
import CustomAppHeader from "@/customization/components/custom-app-header";
import useTheme from "@/customization/hooks/use-custom-theme";

export function DashboardWrapperPage() {
  useTheme();

  return (
    <div className="flex h-screen w-full flex-col overflow-hidden">
      <CustomAppHeader />
      <div className="flex w-full flex-1 flex-row overflow-hidden">
        <Outlet />
      </div>
    </div>
  );
}
