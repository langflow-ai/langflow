import "reactflow/dist/style.css";
import { useState, useEffect, useContext } from "react";
import "./App.css";
import { useLocation } from "react-router-dom";
import _ from "lodash";

import ErrorAlert from "./alerts/error";
import NoticeAlert from "./alerts/notice";
import SuccessAlert from "./alerts/success";
import { alertContext } from "./contexts/alertContext";
import { locationContext } from "./contexts/locationContext";
import { ErrorBoundary } from "react-error-boundary";
import CrashErrorComponent from "./components/CrashErrorComponent";
import { TabsContext } from "./contexts/tabsContext";
import { getVersion } from "./controllers/API";
import Router from "./routes";
import Header from "./components/headerComponent";

export default function App() {
  let { setCurrent, setShowSideBar, setIsStackedOpen } =
    useContext(locationContext);
  let location = useLocation();
  useEffect(() => {
    setCurrent(location.pathname.replace(/\/$/g, "").split("/"));
    setShowSideBar(true);
    setIsStackedOpen(true);
  }, [location.pathname, setCurrent, setIsStackedOpen, setShowSideBar]);
  const { hardReset } = useContext(TabsContext);
  const {
    errorData,
    errorOpen,
    setErrorOpen,
    noticeData,
    noticeOpen,
    setNoticeOpen,
    successData,
    successOpen,
    setSuccessOpen,
  } = useContext(alertContext);

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

  return (
    //need parent component with width and height
    <div className="h-full flex flex-col">
      <ErrorBoundary
        onReset={() => {
          window.localStorage.removeItem("tabsData");
          window.localStorage.clear();
          hardReset();
          window.location.href = window.location.href;
        }}
        FallbackComponent={CrashErrorComponent}
      >
        <Header />
        <Router />
      </ErrorBoundary>
      <div></div>
      <div
        className="flex flex-col-reverse fixed bottom-5 left-5"
        style={{ zIndex: 999 }}
      >
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
