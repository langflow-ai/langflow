export type storeComponent = {
  id: string;
  is_component: boolean;
  tags: { id: string; name: string }[];
  metadata?: {};
  downloads_count: number;
  name: string;
  description: string;
  liked_by_count: number;
};
