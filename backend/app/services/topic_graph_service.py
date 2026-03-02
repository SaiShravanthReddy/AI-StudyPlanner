import re

from app.core.config import Settings
from app.schemas.planner import TopicEdge, TopicGraphResponse, TopicNode
from app.services.embedding_service import EmbeddingService
from app.services.gpt_service import TopicDraft


class TopicGraphService:
    def __init__(self, settings: Settings, embedding_service: EmbeddingService):
        self.settings = settings
        self.embedding_service = embedding_service

    def build_topic_graph(self, course_id: str, topic_drafts: list[TopicDraft]) -> TopicGraphResponse:
        topics = [self._to_topic_node(index=i, draft=draft) for i, draft in enumerate(topic_drafts)]
        title_to_id = {self._norm(topic.title): topic.id for topic in topics}
        edges: list[TopicEdge] = []

        for topic in topics:
            resolved_dependencies = []
            for dep_title in topic.dependencies:
                dep_id = title_to_id.get(self._norm(dep_title))
                if dep_id and dep_id != topic.id:
                    resolved_dependencies.append(dep_id)
                    edges.append(
                        TopicEdge(
                            source=dep_id,
                            target=topic.id,
                            edge_type="dependency",
                            weight=1.0,
                        )
                    )
            topic.dependencies = sorted(set(resolved_dependencies))

        vectors = self.embedding_service.encode([f"{t.title}. {t.description}" for t in topics])
        similarity = self.embedding_service.cosine_similarity_matrix(vectors)
        threshold = self.settings.topic_similarity_threshold
        for i, source in enumerate(topics):
            for j, target in enumerate(topics):
                if i >= j:
                    continue
                score = float(similarity[i][j])
                if score < threshold:
                    continue
                source.similarity_links.append(target.id)
                target.similarity_links.append(source.id)
                edges.append(
                    TopicEdge(
                        source=source.id,
                        target=target.id,
                        edge_type="similarity",
                        weight=round(score, 4),
                    )
                )
        return TopicGraphResponse(course_id=course_id, topics=topics, edges=edges)

    def _to_topic_node(self, index: int, draft: TopicDraft) -> TopicNode:
        slug = re.sub(r"[^a-z0-9]+", "-", draft.title.lower()).strip("-")
        if not slug:
            slug = f"topic-{index + 1}"
        return TopicNode(
            id=f"{slug}-{index + 1}",
            title=draft.title,
            description=draft.description,
            difficulty=max(1, min(5, draft.difficulty)),
            estimated_minutes=max(15, min(600, draft.estimated_minutes)),
            dependencies=draft.dependencies,
        )

    def _norm(self, value: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", "", value.lower())).strip()

