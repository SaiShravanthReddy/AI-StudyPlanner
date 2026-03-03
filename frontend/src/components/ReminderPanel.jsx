export default function ReminderPanel({ reminders }) {
  return (
    <div className="card">
      <div className="section-title">5. Automated Daily Reminders</div>
      {!reminders?.length ? (
        <p className="muted">Reminders will appear after plan generation.</p>
      ) : (
        <ul className="reminder-list">
          {reminders.map((reminder, idx) => (
            <li key={`${reminder}-${idx}`}>{reminder}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

