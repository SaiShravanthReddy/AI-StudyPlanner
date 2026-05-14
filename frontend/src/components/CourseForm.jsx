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
    difficulty_level: "medium",
  });

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    onSubmit({ ...form, end_date: form.end_date || null });
  };

  return (
    <form className="card form-card" onSubmit={handleSubmit}>
      <div className="section-title">Syllabus Intake</div>
      <label>
        Course ID
        <input name="course_id" value={form.course_id} onChange={handleChange} required />
      </label>
      <label>
        Course Title
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
          Start Date
          <input type="date" name="start_date" value={form.start_date} onChange={handleChange} required />
        </label>
        <label>
          End Date
          <input type="date" name="end_date" value={form.end_date} onChange={handleChange} />
        </label>
        <label>
          Difficulty
          <select name="difficulty_level" value={form.difficulty_level} onChange={handleChange}>
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </select>
        </label>
      </div>
      <button className="button-primary" type="submit" disabled={loading}>
        {loading ? "Generating..." : "Generate Study Roadmap"}
      </button>
    </form>
  );
}
