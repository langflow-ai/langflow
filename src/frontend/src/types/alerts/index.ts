export type ErrorAlertType = {
  title: string;
  list: Array<string> | undefined;
  id: string;
  removeAlert: (id: string) => void;
};
export type NoticeAlertType = {
  title: string;
  link: string | undefined;
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
  isDropdown?: boolean;
};

export type RenderALertComponentType = {
  alert: AlertItemType;
}

export type AlertComponentType = {
  alert: AlertItemType;
  setShow: (show: boolean | ((old: boolean) => boolean)) => void;
  removeAlert: (id: string) => void;
  isDropdown: boolean;
}

export type AlertDropdownType = {
  children: JSX.Element;
};
export type AlertItemType = {
  type: "notice" | "error" | "success";
  title: string;
  link?: string;
  list?: Array<string>;
  id: string;
};
