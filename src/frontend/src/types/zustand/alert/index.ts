import { AlertItemType } from "../../alerts";

export type AlertStoreType = {
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
  clearNotificationList: () => void;
  removeFromNotificationList: (index: string) => void;
  loading: boolean;
  setLoading: (newState: boolean) => void;
};
