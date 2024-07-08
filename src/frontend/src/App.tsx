import { useContext, useEffect, useState } from "react";
import { ErrorBoundary } from "react-error-boundary";
import { useNavigate } from "react-router-dom";
import "reactflow/dist/style.css";
import "./App.css";
import AlertDisplayArea from "./alerts/displayArea";
import CrashErrorComponent from "./components/crashErrorComponent";
import FetchErrorComponent from "./components/fetchErrorComponent";
import LoadingComponent from "./components/loadingComponent";
import {
  FETCH_ERROR_DESCRIPION,
  FETCH_ERROR_MESSAGE,
} from "./constants/constants";
import { AuthContext } from "./contexts/authContext";
import { autoLogin } from "./controllers/API";
import { useGetHealthQuery } from "./controllers/API/queries/health";
import { useGetVersionQuery } from "./controllers/API/queries/version";
import { setupAxiosDefaults } from "./controllers/API/utils";
import useTrackLastVisitedPath from "./hooks/use-track-last-visited-path";
import Router from "./routes";
import { Case } from "./shared/components/caseComponent";
import useAlertStore from "./stores/alertStore";
import { useDarkStore } from "./stores/darkStore";
import useFlowsManagerStore from "./stores/flowsManagerStore";
import { useFolderStore } from "./stores/foldersStore";

export default function App() {
  useTrackLastVisitedPath();
  const isLoading = useFlowsManagerStore((state) => state.isLoading);
  const { isAuthenticated, login, setUserData, setAutoLogin, getUser } =
    useContext(AuthContext);
  const setLoading = useAlertStore((state) => state.setLoading);
  const refreshStars = useDarkStore((state) => state.refreshStars);
  const dark = useDarkStore((state) => state.dark);

  useGetVersionQuery();

  const isLoadingFolders = useFolderStore((state) => state.isLoadingFolders);

  const {
    data: healthData,
    isFetching: fetchingHealth,
    isError: isErrorHealth,
    refetch,
  } = useGetHealthQuery();

  useEffect(() => {
    if (!dark) {
      document.getElementById("body")!.classList.remove("dark");
    } else {
      document.getElementById("body")!.classList.add("dark");
    }
  }, [dark]);

  useEffect(() => {
    const abortController = new AbortController();
    const isLoginPage = location.pathname.includes("login");

    autoLogin(abortController.signal)
      .then(async (user) => {
        if (user && user["access_token"]) {
          user["refresh_token"] = "auto";
          login(user["access_token"]);
          setUserData(user);
          setAutoLogin(true);
          fetchAllData();
        }
      })
      .catch(async (error) => {
        if (error.name !== "CanceledError") {
          setAutoLogin(false);
          if (isAuthenticated && !isLoginPage) {
            getUser();
            fetchAllData();
          } else {
            setLoading(false);
            useFlowsManagerStore.setState({ isLoading: false });
          }
        }
      });

    /*
      Abort the request as it isn't needed anymore, the component being
      unmounted. It helps avoid, among other things, the well-known "can't
      perform a React state update on an unmounted component" warning.
    */
    return () => abortController.abort();
  }, []);
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

  const isLoadingApplication = isLoading || isLoadingFolders;

  return (
    //need parent component with width and height
    <div className="flex h-full flex-col">
      <ErrorBoundary
        onReset={() => {
          // any reset function
        }}
        FallbackComponent={CrashErrorComponent}
      >
        <>
          {
            <FetchErrorComponent
              description={FETCH_ERROR_DESCRIPION}
              message={FETCH_ERROR_MESSAGE}
              openModal={
                isErrorHealth ||
                (healthData &&
                  Object.values(healthData).some((value) => value !== "ok"))
              }
              setRetry={() => {
                refetch();
              }}
              isLoadingHealth={fetchingHealth}
            ></FetchErrorComponent>
          }

          <Case condition={isLoadingApplication}>
            <div className="loading-page-panel">
              <LoadingComponent remSize={50} />
            </div>
          </Case>

          <Case condition={!isLoadingApplication}>
            <Router />
          </Case>
        </>
      </ErrorBoundary>
      <div></div>
      <div className="app-div">
        <AlertDisplayArea />
      </div>
    </div>
  );
}
