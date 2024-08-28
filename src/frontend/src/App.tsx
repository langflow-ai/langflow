import { Suspense, useContext, useEffect } from "react";
import { Cookies } from "react-cookie";
import { RouterProvider } from "react-router-dom";
import "reactflow/dist/style.css";
import LoadingComponent from "./components/loadingComponent";
import { AuthContext } from "./contexts/authContext";
import {
  useAutoLogin,
  useRefreshAccessToken,
} from "./controllers/API/queries/auth";
import { useGetVersionQuery } from "./controllers/API/queries/version";
import useSaveConfig from "./hooks/use-save-config";
import router from "./routes";
import useAlertStore from "./stores/alertStore";
import useAuthStore from "./stores/authStore";
import { useDarkStore } from "./stores/darkStore";
import useFlowsManagerStore from "./stores/flowsManagerStore";

export default function App() {
  const { login, setUserData, getUser } = useContext(AuthContext);
  const setAutoLogin = useAuthStore((state) => state.setAutoLogin);
  const setLoading = useAlertStore((state) => state.setLoading);
  const refreshStars = useDarkStore((state) => state.refreshStars);
  const dark = useDarkStore((state) => state.dark);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const cookies = new Cookies();
  const logout = useAuthStore((state) => state.logout);

  const refreshToken = cookies.get("refresh_token");

  const { mutate: mutateAutoLogin } = useAutoLogin();

  const { mutate: mutateRefresh } = useRefreshAccessToken();

  const isLoginPage = location.pathname.includes("login");

  useEffect(() => {
    if (!dark) {
      document.getElementById("body")!.classList.remove("dark");
    } else {
      document.getElementById("body")!.classList.add("dark");
    }
  }, [dark]);

  useEffect(() => {
    mutateAutoLogin(undefined, {
      onSuccess: async (user) => {
        if (user && user["access_token"]) {
          user["refresh_token"] = "auto";
          login(user["access_token"], "auto");
          setUserData(user);
          setAutoLogin(true);
          refreshStars();
          // mutateRefresh({ refresh_token: refreshToken });
        }
      },
      onError: (error) => {
        if (error.name !== "CanceledError") {
          setAutoLogin(false);
          if (!isLoginPage) {
            if (!isAuthenticated) {
              setLoading(false);
              useFlowsManagerStore.setState({ isLoading: false });
              logout();
            } else {
              mutateRefresh({ refresh_token: refreshToken });
              refreshStars();
              getUser();
            }
          }
        }
      },
    });
  }, []);

  useGetVersionQuery();
  useSaveConfig();

  return (
    //need parent component with width and height
    <Suspense
      fallback={
        <div className="loading-page-panel">
          <LoadingComponent remSize={50} />
        </div>
      }
    >
      <RouterProvider router={router} />
    </Suspense>
  );
}
