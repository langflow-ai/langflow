export type ErrorAlertType = {
  title: string;
  list: Array<string>;
  id: string;
  removeAlert: (id: string) => void;
};
export type NoticeAlertType = {
  title: string;
  link: string;
  id: string;
  removeAlert: (id: string) => void;
};
export type SuccessAlertType = {
  title: string;
  id: string;
  removeAlert: (id: string) => void;
};
export type SingleAlertComponentType = {
  dropItem: AlertItemType;
  removeAlert: (index: string) => void;
};
export type AlertDropdownType = {};
export type AlertItemType = {
  type: "notice" | "error" | "success";
  title: string;
  link?: string;
  list?: Array<string>;
  id: string;
};
