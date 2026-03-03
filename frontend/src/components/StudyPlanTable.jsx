export default function StudyPlanTable({ plan }) {
  if (!plan || !plan.items?.length) {
    return (
      <div className="card">
        <div className="section-title">3. Daily Study Schedule</div>
        <p className="muted">No plan generated yet.</p>
      </div>
    );
  }
  return (
    <div className="card">
      <div className="section-title">3. Daily Study Schedule</div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Topic</th>
              <th>Minutes</th>
              <th>Status</th>
              <th>Rationale</th>
            </tr>
          </thead>
          <tbody>
            {plan.items.map((item, index) => (
              <tr key={`${item.topic_id}-${item.date}-${index}`}>
                <td>{item.date}</td>
                <td>{item.topic_title}</td>
                <td>{item.planned_minutes}</td>
                <td>
                  <span className={`pill ${item.status}`}>{item.status}</span>
                </td>
                <td>{item.rationale}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

