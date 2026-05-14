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

  const calcScore = (items) => {
    const weight = { High: 3, Medium: 2, Low: 1 };
    const total = items.reduce((s, i) => s + (weight[i.priority] ?? 1), 0);
    if (!total) return 0;
    const earned = items.reduce((s, item) => {
      const w = weight[item.priority] ?? 1;
      if (item.completed) return s + w;
      if (item.subtopics && item.subtopics.length > 0) {
        const done = item.subtopics.filter((sub) => sub.completed).length;
        return s + w * done / item.subtopics.length;
      }
      return s;
    }, 0);
    return Math.round(earned / total * 1000) / 10;
  };

  const applySubtopicToggle = (items, topicId, subtopicId, newCompleted) =>
    items.map((item) => {
      if (item.id !== topicId) return item;
      const updatedSubs = item.subtopics.map((s) =>
        s.id === subtopicId ? { ...s, completed: newCompleted } : s
      );
      const topicDone = updatedSubs.length > 0 && updatedSubs.every((s) => s.completed);
      return { ...item, subtopics: updatedSubs, completed: topicDone };
    });

  const handleSubtopicToggle = async (topicItem, subtopic) => {
    const newCompleted = !subtopic.completed;
    setRoadmap((prev) => {
      const updatedItems = applySubtopicToggle(prev.items, topicItem.id, subtopic.id, newCompleted);
      return { ...prev, items: updatedItems, completion_score: calcScore(updatedItems) };
    });
    try {
      const { completion_score } = await saveProgress({
        course_id: roadmap.course_id,
        topic_id: topicItem.id,
        subtopic_id: subtopic.id,
        completed: newCompleted,
      });
      setRoadmap((prev) => ({ ...prev, completion_score }));
    } catch {
      setRoadmap((prev) => {
        const revertedItems = applySubtopicToggle(prev.items, topicItem.id, subtopic.id, !newCompleted);
        return { ...prev, items: revertedItems, completion_score: calcScore(revertedItems) };
      });
    }
  };

  const handleToggle = async (item) => {
    const newCompleted = !item.completed;
    setRoadmap((prev) => {
      const updatedItems = prev.items.map((i) =>
        i.id === item.id
          ? { ...i, completed: newCompleted, subtopics: i.subtopics.map((s) => ({ ...s, completed: newCompleted })) }
          : i
      );
      return { ...prev, items: updatedItems, completion_score: calcScore(updatedItems) };
    });
    try {
      const { completion_score } = await saveProgress({
        course_id: roadmap.course_id,
        topic_id: item.id,
        completed: newCompleted,
      });
      setRoadmap((prev) => ({ ...prev, completion_score }));
    } catch {
      setRoadmap((prev) => {
        const revertedItems = prev.items.map((i) =>
          i.id === item.id
            ? { ...i, completed: !newCompleted, subtopics: i.subtopics.map((s) => ({ ...s, completed: !newCompleted })) }
            : i
        );
        return { ...prev, items: revertedItems, completion_score: calcScore(revertedItems) };
      });
    }
  };

  return (
    <div className="layout">
      <header className="hero">
        <h1>AI Study Roadmap Planner</h1>
      </header>
      {error ? <div className="error-banner">{error}</div> : null}
      <CourseForm onSubmit={handleIngest} loading={loading} />
      <RoadmapChecklist roadmap={roadmap} onToggle={handleToggle} onSubtopicToggle={handleSubtopicToggle} />
    </div>
  );
}
