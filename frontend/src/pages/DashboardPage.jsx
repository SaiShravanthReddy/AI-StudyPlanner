import { useMemo, useState } from "react";

import { fetchReminders, ingestSyllabus, replan, saveProgress } from "../api/client";
import CourseForm from "../components/CourseForm";
import ProgressTracker from "../components/ProgressTracker";
import ReminderPanel from "../components/ReminderPanel";
import StudyPlanTable from "../components/StudyPlanTable";
import TopicGraphView from "../components/TopicGraphView";
import { todayIsoDate } from "../utils/date";

export default function DashboardPage() {
  const [loading, setLoading] = useState(false);
  const [graph, setGraph] = useState(null);
  const [plan, setPlan] = useState(null);
  const [activeCourse, setActiveCourse] = useState(null);
  const [reminders, setReminders] = useState([]);
  const [error, setError] = useState("");

  const courseId = useMemo(() => activeCourse?.course_id || "cs-grad-601", [activeCourse]);

  const refreshReminders = async (cid) => {
    try {
      const payload = await fetchReminders(cid);
      setReminders(payload.reminders || []);
    } catch {
      setReminders([]);
    }
  };

  const handleIngest = async (payload) => {
    setLoading(true);
    setError("");
    try {
      const response = await ingestSyllabus(payload);
      setGraph(response.graph);
      setPlan(response.plan);
      setActiveCourse(payload);
      await refreshReminders(payload.course_id);
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to generate plan.");
    } finally {
      setLoading(false);
    }
  };

  const handleProgress = async (payload) => {
    setError("");
    try {
      await saveProgress(payload);
      const replanned = await replan({
        course_id: payload.course_id,
        from_date: todayIsoDate(),
        daily_study_minutes: activeCourse?.daily_study_minutes || 120
      });
      setPlan(replanned);
      await refreshReminders(payload.course_id);
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to save progress or replan.");
    }
  };

  return (
    <div className="layout">
      <header className="hero">
        <h1>AI-Powered Adaptive Study Planner</h1>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}

      <CourseForm onSubmit={handleIngest} loading={loading} />
      <TopicGraphView graph={graph} />
      <StudyPlanTable plan={plan} />
      <ProgressTracker plan={plan} courseId={courseId} onProgress={handleProgress} />
      <ReminderPanel reminders={reminders} />
    </div>
  );
}
