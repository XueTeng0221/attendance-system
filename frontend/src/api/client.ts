import axios, { type AxiosResponse } from "axios";

import { clearAuth, getToken } from "../auth";
import type {
  AttendanceResponse,
  CurrentUser,
  EmotionReport,
  FaceDetectionResponse,
  GroupPhotoResponse,
  LoginResponse,
  ParticipationRow,
  StudentBatchImportResponse,
  Student
} from "../types";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1",
  timeout: 120000
});

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let onUnauthorized: (() => void) | null = null;

export function registerUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler;
}

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      clearAuth();
      onUnauthorized?.();
    }
    return Promise.reject(error);
  }
);

export async function login(username: string, password: string): Promise<LoginResponse> {
  const response = await api.post<LoginResponse>("/auth/login", { username, password });
  return response.data;
}

export async function fetchMe(): Promise<CurrentUser> {
  const response = await api.get<CurrentUser>("/auth/me");
  return response.data;
}

export async function registerStudent(input: {
  studentNo: string;
  name: string;
  className: string;
  password?: string;
  imageFile: File;
}): Promise<Student> {
  const formData = new FormData();
  formData.append("student_no", input.studentNo);
  formData.append("name", input.name);
  formData.append("class_name", input.className);
  if (input.password) {
    formData.append("password", input.password);
  }
  formData.append("image", input.imageFile);

  const response = await api.post<Student>("/students/register", formData);
  return response.data;
}

export async function importStudentsFromDirectory(files: File[]): Promise<StudentBatchImportResponse> {
  const formData = new FormData();
  files.forEach((file) => formData.append("images", file, file.name));
  const response = await api.post<StudentBatchImportResponse>("/students/import-directory", formData);
  return response.data;
}

export async function listStudents(): Promise<Student[]> {
  const response = await api.get<Student[]>("/students");
  return response.data;
}

export async function checkAttendance(blobs: Blob[]): Promise<AttendanceResponse> {
  const formData = new FormData();
  blobs.forEach((blob, idx) => formData.append("images", blob, `frame-${idx}.jpg`));

  const response = await api.post<AttendanceResponse>("/attendance/check", formData);
  return response.data;
}

export async function detectAttendanceFace(blob: Blob): Promise<FaceDetectionResponse> {
  const formData = new FormData();
  formData.append("image", blob, "frame.jpg");
  const response = await api.post<FaceDetectionResponse>("/attendance/detect-face", formData);
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

async function downloadBlob(path: string, filename: string): Promise<void> {
  const response: AxiosResponse<Blob> = await api.get(path, { responseType: "blob" });
  const url = window.URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export async function exportAttendance(format: "xlsx" | "csv"): Promise<void> {
  await downloadBlob(`/reports/attendance/export?format=${format}`, `attendance.${format}`);
}

export async function exportParticipation(format: "xlsx" | "csv"): Promise<void> {
  await downloadBlob(`/reports/participation/export?format=${format}`, `participation.${format}`);
}
