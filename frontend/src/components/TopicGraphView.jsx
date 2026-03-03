export default function TopicGraphView({ graph }) {
  if (!graph) {
    return (
      <div className="card">
        <div className="section-title">2. Topic Graph</div>
        <p className="muted">Upload syllabus to render topic dependencies and similarity links.</p>
      </div>
    );
  }
  const dependencyEdges = graph.edges.filter((edge) => edge.edge_type === "dependency");
  const similarityEdges = graph.edges.filter((edge) => edge.edge_type === "similarity");
  return (
    <div className="card">
      <div className="section-title">2. Topic Graph</div>
      <div className="graph-summary">
        <span>{graph.topics.length} topics</span>
        <span>{dependencyEdges.length} dependencies</span>
        <span>{similarityEdges.length} similarity links</span>
      </div>
      <div className="topic-grid">
        {graph.topics.map((topic) => (
          <article key={topic.id} className="topic-node">
            <header>
              <h4>{topic.title}</h4>
              <span className={`difficulty d${topic.difficulty}`}>D{topic.difficulty}</span>
            </header>
            <p>{topic.description || "No description provided."}</p>
            <div className="meta-row">
              <strong>{topic.estimated_minutes} min</strong>
              <span>{topic.dependencies.length} deps</span>
              <span>{topic.similarity_links.length} related</span>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

