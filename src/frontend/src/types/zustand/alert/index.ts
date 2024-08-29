import { AlertItemType } from "../../alerts";

export type AlertStoreType = {
  errorData: { title: string; list?: Array<string> };
  setErrorData: (newState: { title: string; list?: Array<string> }) => void;
  noticeData: { title: string; link?: string };
  setNoticeData: (newState: { title: string; link?: string }) => void;
  successData: { title: string };
  setSuccessData: (newState: { title: string }) => void;
  notificationCenter: boolean;
  setNotificationCenter: (newState: boolean) => void;
  notificationList: Array<AlertItemType>;
  tempNotificationList: Array<AlertItemType>;
  clearTempNotificationList: () => void;
  removeFromTempNotificationList: (index: string) => void;
  clearNotificationList: () => void;
  removeFromNotificationList: (index: string) => void;
};
