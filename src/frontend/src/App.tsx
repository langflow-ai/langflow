import _ from "lodash";
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
import useFlowsManagerStore from "./stores/flowsManagerStore";
import { useTypesStore } from "./stores/typesStore";

export default function App() {
  const errorData = useAlertStore((state) => state.errorData);
  const errorOpen = useAlertStore((state) => state.errorOpen);
  const setErrorOpen = useAlertStore((state) => state.setErrorOpen);
  const noticeData = useAlertStore((state) => state.noticeData);
  const noticeOpen = useAlertStore((state) => state.noticeOpen);
  const setNoticeOpen = useAlertStore((state) => state.setNoticeOpen);
  const successData = useAlertStore((state) => state.successData);
  const successOpen = useAlertStore((state) => state.successOpen);
  const setSuccessOpen = useAlertStore((state) => state.setSuccessOpen);
  const loading = useAlertStore((state) => state.loading);
  const [fetchError, setFetchError] = useState(false);

  // Initialize state variable for the list of alerts
  const [alertsList, setAlertsList] = useState<
    Array<{
      type: string;
      data: { title: string; list?: Array<string>; link?: string };
      id: string;
    }>
  >([]);

  // Use effect hook to update alertsList when a new alert is added
  useEffect(() => {
    // If there is an error alert open with data, add it to the alertsList
    if (errorOpen && errorData) {
      if (
        alertsList.length > 0 &&
        JSON.stringify(alertsList[alertsList.length - 1].data) ===
          JSON.stringify(errorData)
      ) {
        return;
      }
      setErrorOpen(false);
      setAlertsList((old) => {
        let newAlertsList = [
          ...old,
          { type: "error", data: _.cloneDeep(errorData), id: _.uniqueId() },
        ];
        return newAlertsList;
      });
    }
    // If there is a notice alert open with data, add it to the alertsList
    else if (noticeOpen && noticeData) {
      if (
        alertsList.length > 0 &&
        JSON.stringify(alertsList[alertsList.length - 1].data) ===
          JSON.stringify(noticeData)
      ) {
        return;
      }
      setNoticeOpen(false);
      setAlertsList((old) => {
        let newAlertsList = [
          ...old,
          { type: "notice", data: _.cloneDeep(noticeData), id: _.uniqueId() },
        ];
        return newAlertsList;
      });
    }
    // If there is a success alert open with data, add it to the alertsList
    else if (successOpen && successData) {
      if (
        alertsList.length > 0 &&
        JSON.stringify(alertsList[alertsList.length - 1].data) ===
          JSON.stringify(successData)
      ) {
        return;
      }
      setSuccessOpen(false);
      setAlertsList((old) => {
        let newAlertsList = [
          ...old,
          { type: "success", data: _.cloneDeep(successData), id: _.uniqueId() },
        ];
        return newAlertsList;
      });
    }
  }, [
    _,
    errorData,
    errorOpen,
    noticeData,
    noticeOpen,
    setErrorOpen,
    setNoticeOpen,
    setSuccessOpen,
    successData,
    successOpen,
  ]);

  const removeAlert = (id: string) => {
    setAlertsList((prevAlertsList) =>
      prevAlertsList.filter((alert) => alert.id !== id)
    );
  };

  const { isAuthenticated } = useContext(AuthContext);
  const refreshFlows = useFlowsManagerStore((state) => state.refreshFlows);
  const getTypes = useTypesStore((state) => state.getTypes);
  const refreshVersion = useDarkStore((state) => state.refreshVersion);
  const refreshStars = useDarkStore((state) => state.refreshStars);

  useEffect(() => {
    refreshStars();
    refreshVersion();

    // If the user is authenticated, fetch the types. This code is important to check if the user is auth because of the execution order of the useEffect hooks.
    if (isAuthenticated === true) {
      // get data from db
      getTypes().then(() => {
        refreshFlows();
      });
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
        ) : loading ? (
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
        {alertsList.map((alert) => (
          <div key={alert.id}>
            {alert.type === "error" ? (
              <ErrorAlert
                key={alert.id}
                title={alert.data.title}
                list={alert.data.list}
                id={alert.id}
                removeAlert={removeAlert}
              />
            ) : alert.type === "notice" ? (
              <NoticeAlert
                key={alert.id}
                title={alert.data.title}
                link={alert.data.link}
                id={alert.id}
                removeAlert={removeAlert}
              />
            ) : (
              <SuccessAlert
                key={alert.id}
                title={alert.data.title}
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
