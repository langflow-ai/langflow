export type storeComponent = {
  id: string;
  is_component: boolean;
  tags?: { id: string; name: string }[];
  metadata?: any;
  downloads_count?: number;
  name: string;
  description: string;
  liked_by_count?: number;
  liked_by_user?: boolean;
  user_created?: { username: string };
  last_tested_version?: string;
  private?: boolean;
};

export type StoreComponentResponse = {
  count: number;
  authorized: boolean;
  results: storeComponent[];
};
