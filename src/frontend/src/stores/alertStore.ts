import { uniqueId } from "lodash";
import { create } from "zustand";
import type { AlertItemType } from "../types/alerts";
import type { AlertStoreType } from "../types/zustand/alert";
import { customStringify } from "../utils/reactflowUtils";

const useAlertStore = create<AlertStoreType>((set, get) => ({
  errorData: { title: "", list: [] },
  noticeData: { title: "", link: "" },
  successData: { title: "" },
  notificationCenter: false,
  notificationList: [],
  tempNotificationList: [],
  addNotificationToHistory: (notification: Omit<AlertItemType, "id">) => {
    const newNotification = { ...notification, id: uniqueId() };
    set({
      notificationCenter: true,
      notificationList: [newNotification, ...get().notificationList],
    });
  },
  addNotificationToTempList: (notification: Omit<AlertItemType, "id">) => {
    const newNotification = { ...notification, id: uniqueId() };
    const tempList = get().tempNotificationList;
    if (
      !tempList.some((item) => {
        return (
          customStringify({
            title: item.title,
            type: item.type,
            list: item.list,
            link: item.link,
          }) ===
          customStringify({
            title: newNotification.title,
            type: newNotification.type,
            list: newNotification.list,
            link: newNotification.link,
          })
        );
      })
    ) {
      set({
        tempNotificationList: [newNotification, ...get().tempNotificationList],
      });
    }
  },
  setErrorData: (newState: { title: string; list?: Array<string> }) => {
    if (newState.title && newState.title !== "") {
      set({ errorData: newState });
      const notification: Omit<AlertItemType, "id"> = {
        type: "error",
        title: newState.title,
        list: newState.list,
      };
      get().addNotificationToHistory(notification);
      get().addNotificationToTempList(notification);
    }
  },
  setNoticeData: (newState: { title: string; link?: string }) => {
    if (newState.title && newState.title !== "") {
      set({ noticeData: newState });
      const notification: Omit<AlertItemType, "id"> = {
        type: "notice",
        title: newState.title,
        link: newState.link,
      };
      get().addNotificationToHistory(notification);
      get().addNotificationToTempList(notification);
    }
  },
  setSuccessData: (newState: { title: string }) => {
    if (newState.title && newState.title !== "") {
      set({ successData: newState });
      const notification: Omit<AlertItemType, "id"> = {
        type: "success",
        title: newState.title,
      };
      get().addNotificationToHistory(notification);
      get().addNotificationToTempList(notification);
    }
  },
  setNotificationCenter: (newState: boolean) => {
    set({ notificationCenter: newState });
  },
  clearNotificationList: () => {
    set({ notificationList: [] });
  },
  removeFromNotificationList: (index: string) => {
    set({
      notificationList: get().notificationList.filter(
        (item) => item.id !== index,
      ),
    });
  },
  clearTempNotificationList: () => {
    set({ tempNotificationList: [] });
  },
  removeFromTempNotificationList: (index: string) => {
    set({
      tempNotificationList: get().tempNotificationList.filter(
        (item) => item.id !== index,
      ),
    });
  },
}));

export default useAlertStore;
