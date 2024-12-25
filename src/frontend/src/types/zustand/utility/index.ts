import { Pagination, Tag } from "@/types/utils/types";

export type UtilityStoreType = {
  selectedItems: any[];
  setSelectedItems: (itemId: any) => void;
  healthCheckTimeout: string | null;
  setHealthCheckTimeout: (timeout: string | null) => void;
  playgroundScrollBehaves: ScrollBehavior;
  setPlaygroundScrollBehaves: (behaves: ScrollBehavior) => void;
  maxFileSizeUpload: number;
  setMaxFileSizeUpload: (maxFileSizeUpload: number) => void;
  flowsPagination: Pagination;
  setFlowsPagination: (pagination: Pagination) => void;
  tags: Tag[];
  setTags: (tags: Tag[]) => void;
  featureFlags: Record<string, any>;
  setFeatureFlags: (featureFlags: Record<string, any>) => void;
  chatValueStore: string;
  setChatValueStore: (value: string) => void;
};
