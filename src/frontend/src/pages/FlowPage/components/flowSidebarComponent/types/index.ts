import { APIClassType, APIDataType } from "@/types/api";
import { Dispatch, SetStateAction } from "react";

export interface CategoryGroupProps {
  dataFilter: APIDataType;
  sortedCategories: string[];
  CATEGORIES: {
    display_name: string;
    name: string;
    icon: string;
  }[];
  openCategories: string[];
  setOpenCategories: (categories: string[]) => void;
  search: string;
  nodeColors: {
    [key: string]: string;
  };
  chatInputAdded: boolean;
  onDragStart: (
    event: React.DragEvent<any>,
    data: { type: string; node?: APIClassType },
  ) => void;
  sensitiveSort: (a: string, b: string) => number;
}

export interface SidebarHeaderComponentProps {
  showConfig: boolean;
  setShowConfig: (show: boolean) => void;
  showBeta: boolean;
  setShowBeta: (show: boolean) => void;
  showLegacy: boolean;
  setShowLegacy: (show: boolean) => void;
  searchInputRef: React.RefObject<HTMLInputElement>;
  isInputFocused: boolean;
  search: string;
  handleInputFocus: (event: React.FocusEvent<HTMLInputElement>) => void;
  handleInputBlur: (event: React.FocusEvent<HTMLInputElement>) => void;
  handleInputChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  filterType:
    | {
        source: string | undefined;
        sourceHandle: string | undefined;
        target: string | undefined;
        targetHandle: string | undefined;
        type: string;
        color: string;
      }
    | undefined;
  setFilterEdge: (edge: any[]) => void;
  setFilterData: Dispatch<SetStateAction<APIDataType>>;
  data: APIDataType;
}
