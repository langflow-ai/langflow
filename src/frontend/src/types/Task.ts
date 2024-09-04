export interface Task {
  id: string;
  title: string;
  description: string;
  attachments: string[];
  author_id: string;
  assignee_id: string;
  category: string;
  state: string;
  status: "pending" | "processing" | "completed" | "failed";
  result?: Record<string, any>;
  created_at: string;
  updated_at: string;
}
