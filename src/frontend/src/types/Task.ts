export interface ReviewInfo {
  comment: string;
  reviewer_id: string;
  reviewed_at: string;
}

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
  input_request: any;
  cron_expression: string | null;
  created_at: string;
  updated_at: string;
  review?: ReviewInfo;
  review_history?: ReviewInfo[];
}
