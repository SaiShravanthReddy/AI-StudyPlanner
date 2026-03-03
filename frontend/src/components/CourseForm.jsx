import { useState } from "react";

const templateText = `Week 1: Introduction, scope, and learning outcomes.
Week 2: Core theory, notation, and foundational proofs.
Week 3: Algorithm design patterns and complexity.
Week 4: Data modeling, constraints, and optimization.
Week 5: Midterm prep and review.
Week 6: Advanced topics and case studies.
Week 7: Applied project work and implementation.
Week 8: Final evaluation and synthesis.`;

export default function CourseForm({ onSubmit, loading }) {
  const [form, setForm] = useState({
    user_id: "student-001",
    course_id: "cs-grad-601",
    course_title: "Advanced Computer Science Seminar",
    syllabus_text: templateText,
    start_date: new Date().toISOString().slice(0, 10),
    end_date: "",
    daily_study_minutes: 120
  });

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    const payload = {
      ...form,
      daily_study_minutes: Number(form.daily_study_minutes),
      end_date: form.end_date || null
    };
    onSubmit(payload);
  };

  return (
    <form className="card form-card" onSubmit={handleSubmit}>
      <div className="section-title">1. Syllabus Intake</div>
      <div className="grid two">
        <label>
          User ID
          <input name="user_id" value={form.user_id} onChange={handleChange} required />
        </label>
        <label>
          Course ID
          <input name="course_id" value={form.course_id} onChange={handleChange} required />
        </label>
      </div>
      <label>
        Course title
        <input name="course_title" value={form.course_title} onChange={handleChange} required />
      </label>
      <label>
        Syllabus
        <textarea
          name="syllabus_text"
          value={form.syllabus_text}
          onChange={handleChange}
          rows={8}
          required
        />
      </label>
      <div className="grid three">
        <label>
          Start date
          <input type="date" name="start_date" value={form.start_date} onChange={handleChange} required />
        </label>
        <label>
          End date
          <input type="date" name="end_date" value={form.end_date} onChange={handleChange} />
        </label>
        <label>
          Daily minutes
          <input
            type="number"
            min="30"
            max="480"
            name="daily_study_minutes"
            value={form.daily_study_minutes}
            onChange={handleChange}
            required
          />
        </label>
      </div>
      <button className="button-primary" type="submit" disabled={loading}>
        {loading ? "Generating..." : "Generate Adaptive Plan"}
      </button>
    </form>
  );
}

