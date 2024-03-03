import { useContext, useEffect, useState } from "react";
import "reactflow/dist/style.css";
import "./App.css";

import { ErrorBoundary } from "react-error-boundary";
import ErrorAlert from "./alerts/error";
import NoticeAlert from "./alerts/notice";
import SuccessAlert from "./alerts/success";
import CrashErrorComponent from "./components/CrashErrorComponent";
import FetchErrorComponent from "./components/fetchErrorComponent";
import LoadingComponent from "./components/loadingComponent";
import {
  FETCH_ERROR_DESCRIPION,
  FETCH_ERROR_MESSAGE,
} from "./constants/constants";
import { AuthContext } from "./contexts/authContext";
import { getHealth } from "./controllers/API";
import Router from "./routes";
import useAlertStore from "./stores/alertStore";
import { useDarkStore } from "./stores/darkStore";
import useFlowStore from "./stores/flowStore";
import useFlowsManagerStore from "./stores/flowsManagerStore";
import { useStoreStore } from "./stores/storeStore";
import { useTypesStore } from "./stores/typesStore";

export default function App() {
  const removeFromTempNotificationList = useAlertStore(
    (state) => state.removeFromTempNotificationList
  );
  const tempNotificationList = useAlertStore(
    (state) => state.tempNotificationList
  );
  const [fetchError, setFetchError] = useState(false);
  const isLoading = useFlowsManagerStore((state) => state.isLoading);

  const removeAlert = (id: string) => {
    removeFromTempNotificationList(id);
  };

  const { isAuthenticated } = useContext(AuthContext);
  const refreshFlows = useFlowsManagerStore((state) => state.refreshFlows);
  const fetchApiData = useStoreStore((state) => state.fetchApiData);
  const getTypes = useTypesStore((state) => state.getTypes);
  const refreshVersion = useDarkStore((state) => state.refreshVersion);
  const refreshStars = useDarkStore((state) => state.refreshStars);
  const checkHasStore = useStoreStore((state) => state.checkHasStore);

  useEffect(() => {
    refreshStars();
    refreshVersion();

    // If the user is authenticated, fetch the types. This code is important to check if the user is auth because of the execution order of the useEffect hooks.
    if (isAuthenticated === true) {
      // get data from db
      getTypes().then(() => {
        refreshFlows();
      });
      checkHasStore();
      fetchApiData();
    }
  }, [isAuthenticated]);

  useEffect(() => {
    // Timer to call getHealth every 5 seconds
    const timer = setInterval(() => {
      getHealth()
        .then(() => {
          if (fetchError) setFetchError(false);
        })
        .catch(() => {
          setFetchError(true);
        });
    }, 20000);

    // Clean up the timer on component unmount
    return () => {
      clearInterval(timer);
    };
  }, []);

  return (
    //need parent component with width and height
    <div className="flex h-full flex-col">
      <ErrorBoundary
        onReset={() => {
          // any reset function
        }}
        FallbackComponent={CrashErrorComponent}
      >
        {fetchError ? (
          <FetchErrorComponent
            description={FETCH_ERROR_DESCRIPION}
            message={FETCH_ERROR_MESSAGE}
          ></FetchErrorComponent>
        ) : isLoading ? (
          <div className="loading-page-panel">
            <LoadingComponent remSize={50} />
          </div>
        ) : (
          <>
            <Router />
          </>
        )}
      </ErrorBoundary>
      <div></div>
      <div className="app-div" style={{ zIndex: 999 }}>
        {tempNotificationList.map((alert) => (
          <div key={alert.id}>
            {alert.type === "error" ? (
              <ErrorAlert
                key={alert.id}
                title={alert.title}
                list={alert.list}
                id={alert.id}
                removeAlert={removeAlert}
              />
            ) : alert.type === "notice" ? (
              <NoticeAlert
                key={alert.id}
                title={alert.title}
                link={alert.link}
                id={alert.id}
                removeAlert={removeAlert}
              />
            ) : (
              <SuccessAlert
                key={alert.id}
                title={alert.title}
                id={alert.id}
                removeAlert={removeAlert}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
