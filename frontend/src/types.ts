export type Role = "teacher" | "student";

export interface CurrentUser {
  id: number;
  username: string;
  role: Role;
  student_id: number | null;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: CurrentUser;
}

export interface Student {
  id: number;
  student_no: string;
  name: string;
  class_name: string;
  created_at: string;
}

export interface EmotionResult {
  emotion: string;
  score: number;
}

export interface LivenessBreakdown {
  score?: number;
  passed?: boolean;
  reason?: string;
  single_avg?: number;
  motion?: number;
  motion_raw?: number;
  brightness?: number;
  brightness_var?: number;
  frames?: number;
  moire?: number;
  blur?: number;
  texture?: number;
  color?: number;
}

export interface AttendanceResponse {
  status: "success" | "failed";
  confidence: number;
  liveness_score: number;
  liveness_breakdown: LivenessBreakdown | null;
  reason: string;
  attendance_time: string;
  student: Student | null;
  emotion: EmotionResult;
}

export interface GroupPhotoMatchItem {
  student_id: number;
  student_no: string;
  name: string;
  class_name: string;
  confidence: number;
  emotion: string;
  emotion_score: number;
}

export interface GroupPhotoResponse {
  event_name: string;
  detected_faces: number;
  matched_students: GroupPhotoMatchItem[];
  unmatched_faces: number;
  processing_time_ms: number;
}

export interface ParticipationRow {
  student_id: number;
  student_no: string;
  name: string;
  class_name: string;
  events_count: number;
}

export interface EmotionStatRow {
  emotion: string;
  count: number;
}

export interface EmotionTimelineRow {
  timestamp: string;
  emotion: string;
  source: string;
}

export interface EmotionReport {
  summary: EmotionStatRow[];
  timeline: EmotionTimelineRow[];
}
