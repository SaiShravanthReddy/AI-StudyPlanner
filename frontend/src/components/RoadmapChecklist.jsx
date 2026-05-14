export default function RoadmapChecklist({ roadmap, onToggle, onSubtopicToggle }) {
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
              <>
                {/* Topic row */}
                <tr key={item.id} className={item.completed ? "row-done" : ""}>
                  <td>
                    <input
                      type="checkbox"
                      checked={item.completed}
                      onChange={() => onToggle(item)}
                      title={item.subtopics.length > 0 ? "Auto-completes when all subtopics are done" : undefined}
                    />
                  </td>
                  <td><strong>{item.topic}</strong></td>
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

                {/* Subtopic rows */}
                {item.subtopics.map((sub) => {
                  const subMinutes = Math.round(item.suggested_minutes / item.subtopics.length);
                  return (
                    <tr key={sub.id} className={`subtopic-row${sub.completed ? " row-done" : ""}`}>
                      <td>
                        <input
                          type="checkbox"
                          checked={sub.completed}
                          onChange={() => onSubtopicToggle(item, sub)}
                        />
                      </td>
                      <td className="subtopic-cell">{sub.title}</td>
                      <td className="muted">{item.date}</td>
                      <td className="muted">{subMinutes}</td>
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
                      <td />
                      <td>
                        {sub.resources?.article_url && (
                          <a href={sub.resources.article_url} target="_blank" rel="noreferrer" className="resource-link">
                            📄 {sub.resources.article_title ?? "Article"}
                          </a>
                        )}
                        {sub.resources?.video_url && (
                          <a href={sub.resources.video_url} target="_blank" rel="noreferrer" className="resource-link">
                            ▶ {sub.resources.video_title ?? "Video"}
                          </a>
                        )}
                        {!sub.resources?.article_url && !sub.resources?.video_url && (
                          <span className="muted">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
