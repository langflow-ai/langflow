import { uniqueId } from "lodash";
import { create } from "zustand";
import { AlertItemType } from "../types/alerts";
import { AlertStoreType } from "../types/zustand/alert";
import { customStringify } from "../utils/reactflowUtils";

const pushNotificationList = (
  list: AlertItemType[],
  notification: AlertItemType,
) => {
  list.unshift(notification);
  return list;
};

const useAlertStore = create<AlertStoreType>((set, get) => ({
  errorData: { title: "", list: [] },
  noticeData: { title: "", link: "" },
  successData: { title: "" },
  notificationCenter: false,
  notificationList: [],
  tempNotificationList: [],
  setErrorData: (newState: { title: string; list?: Array<string> }) => {
    if (newState.title && newState.title !== "") {
      set({
        errorData: newState,
        notificationCenter: true,
        notificationList: [
          {
            type: "error",
            title: newState.title,
            list: newState.list,
            id: uniqueId(),
          },
          ...get().notificationList,
        ],
      });
      const tempList = get().tempNotificationList;
      if (
        !tempList.some((item) => {
          return (
            customStringify({
              title: item.title,
              type: item.type,
              list: item.list,
            }) === customStringify({ ...newState, type: "error" })
          );
        })
      ) {
        set({
          tempNotificationList: [
            {
              type: "error",
              title: newState.title,
              list: newState.list,
              id: uniqueId(),
            },
            ...get().tempNotificationList,
          ],
        });
      }
    }
  },
  setNoticeData: (newState: { title: string; link?: string }) => {
    if (newState.title && newState.title !== "") {
      set({
        noticeData: newState,
        notificationCenter: true,
        notificationList: [
          {
            type: "notice",
            title: newState.title,
            link: newState.link,
            id: uniqueId(),
          },
          ...get().notificationList,
        ],
      });
      const tempList = get().tempNotificationList;
      if (
        !tempList.some((item) => {
          return (
            customStringify({
              title: item.title,
              type: item.type,
              link: item.link,
            }) === customStringify({ ...newState, type: "notice" })
          );
        })
      ) {
        set({
          tempNotificationList: [
            {
              type: "notice",
              title: newState.title,
              link: newState.link,
              id: uniqueId(),
            },
            ...get().tempNotificationList,
          ],
        });
      }
    }
  },
  setSuccessData: (newState: { title: string }) => {
    if (newState.title && newState.title !== "") {
      set({
        successData: newState,
        notificationCenter: true,
        notificationList: [
          {
            type: "success",
            title: newState.title,
            id: uniqueId(),
          },
          ...get().notificationList,
        ],
      });
      const tempList = get().tempNotificationList;
      if (
        !tempList.some((item) => {
          return (
            customStringify({ title: item.title, type: item.type }) ===
            customStringify({ ...newState, type: "success" })
          );
        })
      ) {
        set({
          tempNotificationList: [
            {
              type: "success",
              title: newState.title,
              id: uniqueId(),
            },
            ...get().tempNotificationList,
          ],
        });
      }
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
