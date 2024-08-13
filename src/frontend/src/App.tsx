import { Suspense, useContext, useEffect } from "react";
import { Cookies } from "react-cookie";
import { RouterProvider } from "react-router-dom";
import "reactflow/dist/style.css";
import LoadingComponent from "./components/loadingComponent";
import {
  LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS,
  LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS_ENV,
} from "./constants/constants";
import { AuthContext } from "./contexts/authContext";
import {
  useAutoLogin,
  useRefreshAccessToken,
} from "./controllers/API/queries/auth";
import { useGetVersionQuery } from "./controllers/API/queries/version";
import { setupAxiosDefaults } from "./controllers/API/utils";
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

  useGetVersionQuery();

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
          fetchAllData();
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
              fetchAllData();
              getUser();
            }
          }
        }
      },
    });
  }, []);

  useEffect(() => {
    const envRefreshTime = LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS_ENV;
    const automaticRefreshTime = LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS;

    const accessTokenTimer = isNaN(envRefreshTime)
      ? automaticRefreshTime
      : envRefreshTime;

    const intervalId = setInterval(() => {
      if (isAuthenticated && !isLoginPage) {
        mutateRefresh({ refresh_token: refreshToken });
      }
    }, accessTokenTimer * 1000);

    return () => clearInterval(intervalId);
  }, [isLoginPage]);

  const fetchAllData = async () => {
    setTimeout(async () => {
      await Promise.all([refreshStars(), fetchData()]);
    }, 1000);
  };

  const fetchData = async () => {
    return new Promise<void>(async (resolve, reject) => {
      if (isAuthenticated) {
        try {
          await setupAxiosDefaults();
          resolve();
        } catch (error) {
          console.error("Failed to fetch data:", error);
          reject();
        }
      }
    });
  };

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
