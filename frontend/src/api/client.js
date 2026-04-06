import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";
const authToken = import.meta.env.VITE_AUTH_TOKEN || "";

const http = axios.create({
  baseURL
});

if (authToken) {
  http.defaults.headers.common.Authorization = `Bearer ${authToken}`;
}

export async function ingestSyllabus(payload) {
  const { data } = await http.post("/syllabus/ingest", payload);
  return data;
}

export async function fetchPlan(userId, courseId) {
  const { data } = await http.get(`/plan/${encodeURIComponent(userId)}/${encodeURIComponent(courseId)}`);
  return data;
}

export async function saveProgress(payload) {
  const { data } = await http.post("/progress", payload);
  return data;
}

export async function replan(payload) {
  const { data } = await http.post("/plan/replan", payload);
  return data;
}

export async function fetchReminders(userId, courseId) {
  const { data } = await http.get(`/reminders/${encodeURIComponent(userId)}/${encodeURIComponent(courseId)}`);
  return data;
}
