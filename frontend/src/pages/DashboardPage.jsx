import { useState } from "react";

import { ingestSyllabus, saveProgress } from "../api/client";
import CourseForm from "../components/CourseForm";
import RoadmapChecklist from "../components/RoadmapChecklist";

export default function DashboardPage() {
  const [loading, setLoading] = useState(false);
  const [roadmap, setRoadmap] = useState(null);
  const [error, setError] = useState("");

  const handleIngest = async (payload) => {
    setLoading(true);
    setError("");
    try {
      const { roadmap: generated } = await ingestSyllabus(payload);
      setRoadmap(generated);
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to generate roadmap.");
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = async (item) => {
    const newCompleted = !item.completed;
    setRoadmap((prev) => ({
      ...prev,
      items: prev.items.map((i) => (i.id === item.id ? { ...i, completed: newCompleted } : i)),
    }));
    try {
      await saveProgress({ course_id: roadmap.course_id, topic_id: item.id, completed: newCompleted });
    } catch {
      setRoadmap((prev) => ({
        ...prev,
        items: prev.items.map((i) => (i.id === item.id ? { ...i, completed: !newCompleted } : i)),
      }));
    }
  };

  return (
    <div className="layout">
      <header className="hero">
        <h1>AI Study Roadmap Planner</h1>
      </header>
      {error ? <div className="error-banner">{error}</div> : null}
      <CourseForm onSubmit={handleIngest} loading={loading} />
      <RoadmapChecklist roadmap={roadmap} onToggle={handleToggle} />
    </div>
  );
}
