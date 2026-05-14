import { useState } from "react";

import { todayIsoDate } from "../utils/date";

const templateText = `Representational power of Multi-layer Perceptrons
Worked out example of the Exclusive-OR network
Gradient of a function; Gradient descent/ascent
The logistic function and its derivative
Logistic regression/Gradient descent for a single neuron
Error back-propagation for multi layer networks
The vanishing gradient problem; ReLU, Leaky ReLU, Soft-Max`;

export default function CourseForm({ onSubmit, loading }) {
  const [form, setForm] = useState({
    course_id: "CAP 6610",
    course_title: "Machine Learning",
    syllabus_text: templateText,
    start_date: todayIsoDate(),
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
      <label>
        Course ID
        <input name="course_id" value={form.course_id} onChange={handleChange} required />
      </label>
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
