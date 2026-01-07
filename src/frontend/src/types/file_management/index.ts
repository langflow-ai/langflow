export type FileType = {
  id: string;
  user_id: string;
  provider: string;
  name: string;
  updated_at?: string;
  path: string;
  created_at: string;
  size: number;
  progress?: number;
  file?: File;
  type?: string;
  disabled?: boolean;
};
