import { Suspense, useEffect } from "react";
import { RouterProvider } from "react-router-dom";
import "reactflow/dist/style.css";
import { useGetAutoLogin } from "./controllers/API/queries/auth";
import { useGetConfig } from "./controllers/API/queries/config/use-get-config";
import { useGetVersionQuery } from "./controllers/API/queries/version";
import { LoadingPage } from "./pages/LoadingPage";
import router from "./routes";
import { useDarkStore } from "./stores/darkStore";

export default function App() {
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
    <Suspense fallback={<LoadingPage />}>
      {isFetched ? <RouterProvider router={router} /> : <LoadingPage />}
    </Suspense>
  );
}
