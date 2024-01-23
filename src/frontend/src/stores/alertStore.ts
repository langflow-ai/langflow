import { uniqueId } from "lodash";
import { create } from "zustand";
import { AlertItemType } from "../types/alerts";
import { AlertStoreType } from "../types/zustand/alert";

const pushNotificationList = (
  list: AlertItemType[],
  notification: AlertItemType
) => {
  list.unshift(notification);
  return list;
};

const useAlertStore = create<AlertStoreType>((set, get) => ({
  errorData: { title: "", list: [] },
  errorOpen: false,
  noticeData: { title: "", link: "" },
  noticeOpen: false,
  successData: { title: "" },
  successOpen: false,
  notificationCenter: false,
  notificationList: [],
  loading: true,
  setErrorData: (newState: { title: string; list?: Array<string> }) => {
    if (newState.title && newState.title !== "") {
      set({
        errorData: newState,
        errorOpen: true,
        notificationCenter: true,
        notificationList: pushNotificationList(get().notificationList, {
          type: "error",
          title: newState.title,
          list: newState.list,
          id: uniqueId(),
        }),
      });
    }
  },
  setErrorOpen: (newState: boolean) => {
    set({ errorOpen: newState });
  },
  setNoticeData: (newState: { title: string; link?: string }) => {
    if (newState.title && newState.title !== "") {
      set({
        noticeData: newState,
        noticeOpen: true,
        notificationCenter: true,
        notificationList: pushNotificationList(get().notificationList, {
          type: "notice",
          title: newState.title,
          link: newState.link,
          id: uniqueId(),
        }),
      });
    }
  },
  setNoticeOpen: (newState: boolean) => {
    set({ noticeOpen: newState });
  },
  setSuccessData: (newState: { title: string }) => {
    if (newState.title && newState.title !== "") {
      set({
        successData: newState,
        successOpen: true,
        notificationCenter: true,
        notificationList: pushNotificationList(get().notificationList, {
          type: "success",
          title: newState.title,
          id: uniqueId(),
        }),
      });
    }
  },
  setSuccessOpen: (newState: boolean) => {
    set({ successOpen: newState });
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
        (item) => item.id !== index
      ),
    });
  },
  setLoading: (newState: boolean) => {
    set({ loading: newState });
  },
}));

export default useAlertStore;
