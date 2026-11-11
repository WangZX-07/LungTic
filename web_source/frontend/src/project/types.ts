export type ProjectRole = "project_admin" | "project_lead" | "team_lead" | "contributor" | "observer" | "unassigned";

export interface ProjectMember {
  id: number;
  name: string;
  avatar_url?: string | null;
  role: ProjectRole;
  mapped_role: ProjectRole;
  manual_role?: ProjectRole | null;
  department_ids: string[];
  department_names: string[];
  job_title_id?: string | null;
  job_title_name?: string | null;
  github_login?: string | null;
  active: boolean;
  last_synced_at?: string | null;
}

export interface Milestone {
  id: number; title: string; description?: string | null; status: string; weight: number;
  start_date?: string | null; due_date?: string | null; sort_order: number; progress: number;
}

export interface ProjectTask {
  id: number; milestone_id?: number | null; title: string; description?: string | null;
  status: string; priority: string; assignee_member_id?: number | null; assignee_name?: string | null;
  due_date?: string | null; weight: number; progress: number; github_issue_number?: number | null;
  github_pr_number?: number | null; github_url?: string | null; updated_at: string;
}

export interface ProgressUpdate {
  id: number; task_id?: number | null; task_title?: string | null; member_id: number; member_name: string;
  progress?: number | null; completed: string; next_steps?: string | null; blockers?: string | null;
  evidence_url?: string | null; created_at: string;
}
