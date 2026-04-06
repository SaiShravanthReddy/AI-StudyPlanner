import { useMemo, useState } from "react";

import { todayIsoDate } from "../utils/date";

export default function ProgressTracker({ plan, userId, courseId, onProgress }) {
  const [selectedTopic, setSelectedTopic] = useState("");
  const [minutesSpent, setMinutesSpent] = useState(60);
  const [completed, setCompleted] = useState(true);
  const topicOptions = useMemo(() => {
    if (!plan?.items?.length) return [];
    const seen = new Set();
    return plan.items
      .filter((item) => {
        if (seen.has(item.topic_id)) return false;
        seen.add(item.topic_id);
        return true;
      })
      .map((item) => ({ id: item.topic_id, title: item.topic_title }));
  }, [plan]);

  if (!topicOptions.length) {
    return (
      <div className="card">
        <div className="section-title">4. Progress Tracking</div>
        <p className="muted">Generate a plan to update progress.</p>
      </div>
    );
  }

  const submit = (event) => {
    event.preventDefault();
    const topicId = selectedTopic || topicOptions[0].id;
    onProgress({
      user_id: userId,
      course_id: courseId,
      topic_id: topicId,
      date: todayIsoDate(),
      minutes_spent: Number(minutesSpent),
      completed
    });
  };

  return (
    <form className="card" onSubmit={submit}>
      <div className="section-title">4. Progress Tracking</div>
      <div className="grid three">
        <label>
          Topic
          <select value={selectedTopic} onChange={(event) => setSelectedTopic(event.target.value)}>
            {topicOptions.map((topic) => (
              <option key={topic.id} value={topic.id}>
                {topic.title}
              </option>
            ))}
          </select>
        </label>
        <label>
          Minutes spent
          <input
            type="number"
            min="0"
            max="600"
            value={minutesSpent}
            onChange={(event) => setMinutesSpent(event.target.value)}
          />
        </label>
        <label>
          Completed
          <select value={completed ? "yes" : "no"} onChange={(event) => setCompleted(event.target.value === "yes")}>
            <option value="yes">Yes</option>
            <option value="no">No</option>
          </select>
        </label>
      </div>
      <button type="submit" className="button-secondary">
        Save Progress + Trigger Adaptive Replan
      </button>
    </form>
  );
}
