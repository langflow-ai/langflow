import { createContext, ReactNode, useState } from "react";
import { AlertItemType } from "../types/alerts";

import _ from "lodash";

//types for alertContextType
type alertContextType = {
  errorData: { title: string; list?: Array<string> };
  setErrorData: (newState: { title: string; list?: Array<string> }) => void;
  errorOpen: boolean;
  setErrorOpen: (newState: boolean) => void;
  noticeData: { title: string; link?: string };
  setNoticeData: (newState: { title: string; link?: string }) => void;
  noticeOpen: boolean;
  setNoticeOpen: (newState: boolean) => void;
  successData: { title: string };
  setSuccessData: (newState: { title: string }) => void;
  successOpen: boolean;
  setSuccessOpen: (newState: boolean) => void;
  notificationCenter: boolean;
  setNotificationCenter: (newState: boolean) => void;
  notificationList: Array<AlertItemType>;
  pushNotificationList: (Object: AlertItemType) => void;
  clearNotificationList: () => void;
  removeFromNotificationList: (index: string) => void;
};

//initial values to alertContextType
const initialValue: alertContextType = {
  errorData: { title: "", list: [] },
  setErrorData: () => {},
  errorOpen: false,
  setErrorOpen: () => {},
  noticeData: { title: "", link: "" },
  setNoticeData: () => {},
  noticeOpen: false,
  setNoticeOpen: () => {},
  successData: { title: "" },
  setSuccessData: () => {},
  successOpen: false,
  setSuccessOpen: () => {},
  notificationCenter: false,
  setNotificationCenter: () => {},
  notificationList: [],
  pushNotificationList: () => {},
  clearNotificationList: () => {},
  removeFromNotificationList: () => {},
};

export const alertContext = createContext<alertContextType>(initialValue);

export function AlertProvider({ children }: { children: ReactNode }) {
  const [errorData, setErrorDataState] = useState<{
    title: string;
    list?: Array<string>;
  }>({ title: "", list: [] });
  const [errorOpen, setErrorOpen] = useState(false);
  const [noticeData, setNoticeDataState] = useState<{
    title: string;
    link?: string;
  }>({ title: "", link: "" });
  const [noticeOpen, setNoticeOpen] = useState(false);
  const [successData, setSuccessDataState] = useState<{ title: string }>({
    title: "",
  });
  const [successOpen, setSuccessOpen] = useState(false);
  const [notificationCenter, setNotificationCenter] = useState(false);
  const [notificationList, setNotificationList] = useState([]);
  const pushNotificationList = (notification: AlertItemType) => {
    setNotificationList((old) => {
      let newNotificationList = _.cloneDeep(old);
      newNotificationList.unshift(notification);
      return newNotificationList;
    });
  };
  /**
   * Sets the error data state, opens the error dialog and pushes the new error notification to the notification list
   * @param newState An object containing the new error data, including title and optional list of error messages
   */
  function setErrorData(newState: { title: string; list?: Array<string> }) {
    setErrorDataState(newState);
    setErrorOpen(true);
    if (newState.title) {
      setNotificationCenter(true);
      pushNotificationList({
        type: "error",
        title: newState.title,
        list: newState.list,
        id: _.uniqueId(),
      });
    }
  }
  /**
   * Sets the state of the notice data and opens the notice modal, also adds a new notice to the notification center if the title is defined.
   * @param newState An object containing the title of the notice and optionally a link.
   */
  function setNoticeData(newState: { title: string; link?: string }) {
    setNoticeDataState(newState);
    setNoticeOpen(true);
    if (newState.title) {
      // Add new notice to notification center
      setNotificationCenter(true);
      pushNotificationList({
        type: "notice",
        title: newState.title,
        link: newState.link,
        id: _.uniqueId(),
      });
    }
  }
  /**
   * Update the success data state and show a success alert notification.
   * @param newState - A state object with a "title" property to set in the success data state.
   */
  function setSuccessData(newState: { title: string }) {
    setSuccessDataState(newState); // update the success data state with the provided new state
    setSuccessOpen(true); // open the success alert

    // If the new state has a "title" property, add a new success notification to the list
    if (newState.title) {
      setNotificationCenter(true); // show the notification center
      pushNotificationList({
        // add the new notification to the list
        type: "success",
        title: newState.title,
        id: _.uniqueId(),
      });
    }
  }
  function clearNotificationList() {
    setNotificationList([]);
  }
  function removeFromNotificationList(index: string) {
    // set the notification list to a new array that filters out the alert with the matching id
    setNotificationList((prevAlertsList) =>
      prevAlertsList.filter((alert) => alert.id !== index)
    );
  }
  return (
    <alertContext.Provider
      value={{
        removeFromNotificationList,
        clearNotificationList,
        notificationList,
        pushNotificationList,
        setNotificationCenter,
        notificationCenter,
        errorData,
        setErrorData,
        errorOpen,
        setErrorOpen,
        noticeData,
        setNoticeData,
        noticeOpen,
        setNoticeOpen,
        successData,
        setSuccessData,
        successOpen,
        setSuccessOpen,
      }}
    >
      {children}
    </alertContext.Provider>
  );
}
