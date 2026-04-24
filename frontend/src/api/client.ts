import axios from "axios";

import type {
  AttendanceResponse,
  EmotionReport,
  GroupPhotoResponse,
  ParticipationRow,
  Student
} from "../types";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1",
  timeout: 20000
});

export async function registerStudent(input: {
  studentNo: string;
  name: string;
  className: string;
  imageFile: File;
}): Promise<Student> {
  const formData = new FormData();
  formData.append("student_no", input.studentNo);
  formData.append("name", input.name);
  formData.append("class_name", input.className);
  formData.append("image", input.imageFile);

  const response = await api.post<Student>("/students/register", formData);
  return response.data;
}

export async function listStudents(): Promise<Student[]> {
  const response = await api.get<Student[]>("/students");
  return response.data;
}

export async function checkAttendance(file: Blob): Promise<AttendanceResponse> {
  const formData = new FormData();
  formData.append("image", file, "attendance.jpg");

  const response = await api.post<AttendanceResponse>("/attendance/check", formData);
  return response.data;
}

export async function recognizeGroupPhoto(input: {
  eventName: string;
  imageFile: File;
}): Promise<GroupPhotoResponse> {
  const formData = new FormData();
  formData.append("event_name", input.eventName);
  formData.append("image", input.imageFile);

  const response = await api.post<GroupPhotoResponse>("/group-photo/recognize", formData);
  return response.data;
}

export async function getParticipationReport(): Promise<ParticipationRow[]> {
  const response = await api.get<ParticipationRow[]>("/reports/participation");
  return response.data;
}

export async function getEmotionReport(): Promise<EmotionReport> {
  const response = await api.get<EmotionReport>("/reports/emotions");
  return response.data;
}
