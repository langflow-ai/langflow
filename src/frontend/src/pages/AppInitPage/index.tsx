import { useGetAutoLogin } from "@/controllers/API/queries/auth";
import { useGetConfig } from "@/controllers/API/queries/config/use-get-config";
import { useGetVersionQuery } from "@/controllers/API/queries/version";
import { useDarkStore } from "@/stores/darkStore";
import { useEffect } from "react";
import { Outlet } from "react-router-dom";
import { LoadingPage } from "../LoadingPage";

export function AppInitPage() {
  const dark = useDarkStore((state) => state.dark);
  const refreshStars = useDarkStore((state) => state.refreshStars);

  const { isFetched } = useGetAutoLogin();
  useGetVersionQuery({ enabled: isFetched });
  useGetConfig({ enabled: isFetched });

  useEffect(() => {
    if (isFetched) {
      refreshStars();
    }
  }, [isFetched]);

  useEffect(() => {
    if (!dark) {
      document.getElementById("body")!.classList.remove("dark");
    } else {
      document.getElementById("body")!.classList.add("dark");
    }
  }, [dark]);

  return (
    //need parent component with width and height
    isFetched ? <Outlet /> : <LoadingPage />
  );
}
