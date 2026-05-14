import re
from collections import defaultdict

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
        topic_by_id = {topic.id: topic for topic in topics}
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
        threshold = self.settings.topic_similarity_threshold
        neighbor_limit = max(0, self.settings.max_similarity_neighbors)
        pair_scores = self._top_similarity_pairs(topics, vectors, threshold, neighbor_limit)
        for (source_id, target_id), score in sorted(pair_scores.items()):
            source = topic_by_id[source_id]
            target = topic_by_id[target_id]
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

    def _top_similarity_pairs(
        self,
        topics: list[TopicNode],
        vectors,
        threshold: float,
        neighbor_limit: int,
    ) -> dict[tuple[str, str], float]:
        if neighbor_limit == 0 or len(topics) < 2:
            return {}
        top_neighbors: dict[str, list[tuple[float, str]]] = defaultdict(list)
        for i, source in enumerate(topics):
            source_vector = vectors[i]
            for j in range(i + 1, len(topics)):
                target = topics[j]
                score = float(source_vector @ vectors[j])
                if score < threshold:
                    continue
                top_neighbors[source.id].append((score, target.id))
                top_neighbors[target.id].append((score, source.id))

        candidate_pairs: dict[tuple[str, str], float] = {}
        for source_id, candidates in top_neighbors.items():
            for score, target_id in sorted(candidates, reverse=True)[:neighbor_limit]:
                pair = tuple(sorted((source_id, target_id)))
                candidate_pairs[pair] = max(score, candidate_pairs.get(pair, score))
        retained_pairs: dict[tuple[str, str], float] = {}
        usage: dict[str, int] = defaultdict(int)
        for pair, score in sorted(candidate_pairs.items(), key=lambda item: (-item[1], item[0])):
            source_id, target_id = pair
            if usage[source_id] >= neighbor_limit or usage[target_id] >= neighbor_limit:
                continue
            retained_pairs[pair] = score
            usage[source_id] += 1
            usage[target_id] += 1
        return retained_pairs

    def _to_topic_node(self, index: int, draft: TopicDraft) -> TopicNode:
        slug = re.sub(r"[^a-z0-9]+", "-", draft.title.lower()).strip("-")
        if not slug:
            slug = f"topic-{index + 1}"
        return TopicNode(
            id=f"{slug}-{index + 1}",
            title=draft.title,
            subtopics=draft.subtopics,
            description=draft.description,
            difficulty=max(1, min(5, draft.difficulty)),
            estimated_minutes=max(15, min(600, draft.estimated_minutes)),
            dependencies=draft.dependencies,
        )

    def _norm(self, value: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", "", value.lower())).strip()
