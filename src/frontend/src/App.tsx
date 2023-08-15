import _ from "lodash";
import { useContext, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import "reactflow/dist/style.css";
import "./App.css";

import { ErrorBoundary } from "react-error-boundary";
import ErrorAlert from "./alerts/error";
import NoticeAlert from "./alerts/notice";
import SuccessAlert from "./alerts/success";
import CrashErrorComponent from "./components/CrashErrorComponent";
import Header from "./components/headerComponent";
import { alertContext } from "./contexts/alertContext";
import { AuthContext } from "./contexts/authContext";
import { locationContext } from "./contexts/locationContext";
import { TabsContext } from "./contexts/tabsContext";
import { getLoggedUser, onLogin } from "./controllers/API";
import Router from "./routes";
import { LOCALHOST_JWT } from "./constants/constants";
import { LoginType } from "./types/api";

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
    setErrorData
  } = useContext(alertContext);
  const navigate = useNavigate();

  // Initialize state variable for the list of alerts
  const [alertsList, setAlertsList] = useState<
    Array<{
      type: string;
      data: { title: string; list?: Array<string>; link?: string };
      id: string;
    }>
  >([]);

  const isLoginPage = location.pathname.includes("login");
  const isAdminPage = location.pathname.includes("admin");
  const isSignUpPage = location.pathname.includes("signup");
  const isLocalHost = window.location.href.includes("localhost");

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

  //this function is to get the user logged in when the page is refreshed
  const { setUserData, getAuthentication, login } = useContext(AuthContext);
  useEffect(() => {
    setTimeout(() => {
      if (getAuthentication && !isLoginPage) {
        getLoggedUser()
          .then((user) => {
            setUserData(user);
          })
          .catch((error) => {});
      }
    }, 1000);
  }, []);

  useEffect(() => {

    if(LOCALHOST_JWT === true && isLocalHost === true){
      const user: LoginType = {
        username: "superuser",
        password: "12345",
      };
      onLogin(user)
        .then((user) => {
          login(user.access_token, user.refresh_token);
          getUser();
          navigate("/");
        })
        .catch((error) => {
          setErrorData({
            title: "Error signing in",
            list: [error["response"]["data"]["detail"]],
          });
        });
    }
  }, [])

  function getUser() {
    if (getAuthentication) {
      setTimeout(() => {
        getLoggedUser()
          .then((user) => {
            setUserData(user);
          })
          .catch((error) => {});
      }, 1000);
    }
  }

  return (
    //need parent component with width and height
    <div className="flex h-full flex-col">
      <ErrorBoundary
        onReset={() => {
          window.localStorage.removeItem("tabsData");
          window.localStorage.clear();
          hardReset();
          window.location.href = window.location.href;
        }}
        FallbackComponent={CrashErrorComponent}
      >
        {!isLoginPage && !isSignUpPage && <Header />}
        <Router />
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
