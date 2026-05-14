export default function RoadmapChecklist({ roadmap, onToggle }) {
  if (!roadmap) {
    return (
      <div className="card">
        <div className="section-title">Study Roadmap</div>
        <p className="muted">Generate a plan to see your roadmap.</p>
      </div>
    );
  }

  const total = roadmap.items.length;
  const done = roadmap.items.filter((i) => i.completed).length;
  const score = roadmap.completion_score ?? 0;

  return (
    <div className="card">
      <div className="section-title">Study Roadmap</div>

      <div className="completion-block">
        <div className="completion-label">
          Completion: <strong>{score}%</strong>&ensp;({done} / {total} topics)
        </div>
        <div className="completion-bar-track">
          <div className="completion-bar-fill" style={{ width: `${score}%` }} />
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Done</th>
              <th>Topic</th>
              <th>Date</th>
              <th>Time (min)</th>
              <th>Difficulty</th>
              <th>Priority</th>
              <th>Depends On</th>
              <th>Resources</th>
            </tr>
          </thead>
          <tbody>
            {roadmap.items.map((item) => (
              <tr key={item.id} className={item.completed ? "row-done" : ""}>
                <td>
                  <input
                    type="checkbox"
                    checked={item.completed}
                    onChange={() => onToggle(item)}
                  />
                </td>
                <td>{item.topic}</td>
                <td>{item.date}</td>
                <td>{item.suggested_minutes}</td>
                <td>
                  <span className={`badge diff-${item.difficulty.toLowerCase()}`}>
                    {item.difficulty}
                  </span>
                </td>
                <td>
                  <span className={`badge prio-${item.priority.toLowerCase()}`}>
                    {item.priority}
                  </span>
                </td>
                <td className="muted">{item.dependency ?? "—"}</td>
                <td>
                  {item.resources?.article_url && (
                    <a href={item.resources.article_url} target="_blank" rel="noreferrer" className="resource-link">
                      📄 {item.resources.article_title ?? "Article"}
                    </a>
                  )}
                  {item.resources?.video_url && (
                    <a href={item.resources.video_url} target="_blank" rel="noreferrer" className="resource-link">
                      ▶ {item.resources.video_title ?? "Video"}
                    </a>
                  )}
                  {!item.resources?.article_url && !item.resources?.video_url && (
                    <span className="muted">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
