import { ReactFlowInstance } from "reactflow";
import { APIClassType } from "../api";
import { AlertItemType } from "../alerts";

const types: { [char: string]: string } = {};
const template: { [char: string]: APIClassType } = {};
const data: { [char: string]: string } = {};

export type typesContextType = {
  reactFlowInstance: ReactFlowInstance | null;
  setReactFlowInstance: any;
  deleteNode: (idx: string) => void;
  types: typeof types;
  setTypes: (newState: {}) => void;
  templates: typeof template;
  setTemplates: (newState: {}) => void;
  data: typeof data;
  setData: (newState: {}) => void;
};

export type alertContextType = {
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

export type darkContextType = {
  dark: {};
  setDark: (newState: {}) => void;
};

export type locationContextType = {
  current: Array<string>;
  setCurrent: (newState: Array<string>) => void;
  isStackedOpen: boolean;
  setIsStackedOpen: (newState: boolean) => void;
  showSideBar: boolean;
  setShowSideBar: (newState: boolean) => void;
  extraNavigation: {
    title: string;
    options?: Array<{
      name: string;
      href: string;
      icon: any;
      children?: Array<any>;
    }>;
  };
  setExtraNavigation: (newState: {
    title: string;
    options?: Array<{
      name: string;
      href: string;
      icon: any;
      children?: Array<any>;
    }>;
  }) => void;
  extraComponent: any;
  setExtraComponent: (newState: any) => void;
};
