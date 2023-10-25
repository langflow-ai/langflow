import { Edge, Node, ReactFlowInstance } from "reactflow";
import { AlertItemType } from "../alerts";
import { APIClassType, APIDataType } from "../api";

const types: { [char: string]: string } = {};
const template: { [char: string]: APIClassType } = {};
const data: { [char: string]: string } = {};

export type typesContextType = {
  reactFlowInstance: ReactFlowInstance | null;
  setReactFlowInstance: (newState: ReactFlowInstance) => void;
  deleteNode: (idx: string | Array<string>) => void;
  types: typeof types;
  setTypes: (newState: {}) => void;
  templates: typeof template;
  setTemplates: (newState: {}) => void;
  data: APIDataType;
  setData: (newState: {}) => void;
  fetchError: boolean;
  setFetchError: (newState: boolean) => void;
  setFilterEdge: (newState) => void;
  getFilterEdge: any[];
  deleteEdge: (idx: string | Array<string>) => void;
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
  loading: boolean;
  setLoading: (newState: boolean) => void;
};

export type darkContextType = {
  dark: {};
  setDark: (newState: {}) => void;
  stars: number;
  setStars: (stars: number) => void;
  gradientIndex: number;
  setGradientIndex: (index: number) => void;
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
      icon: React.ElementType;
      children?: Array<JSX.Element>;
    }>;
  };
  setExtraNavigation: (newState: {
    title: string;
    options?: Array<{
      name: string;
      href: string;
      icon: React.ElementType;
      children?: Array<JSX.Element>;
    }>;
  }) => void;
  extraComponent: any;
  setExtraComponent: (newState: JSX.Element) => void;
};

export type undoRedoContextType = {
  undo: () => void;
  redo: () => void;
  takeSnapshot: () => void;
};

export type UseUndoRedoOptions = {
  maxHistorySize: number;
  enableShortcuts: boolean;
};

export type UseUndoRedo = (options?: UseUndoRedoOptions) => {
  undo: () => void;
  redo: () => void;
  takeSnapshot: () => void;
  canUndo: boolean;
  canRedo: boolean;
};

export type HistoryItem = {
  nodes: Node[];
  edges: Edge[];
};
