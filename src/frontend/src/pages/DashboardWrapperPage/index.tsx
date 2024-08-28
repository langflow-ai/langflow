import Header from "@/components/headerComponent";
import { Outlet } from "react-router-dom";

export function DashboardWrapperPage() {
  return (
    <div className="flex h-screen w-full flex-col">
      <Header />
      <Outlet />
    </div>
  );
}
