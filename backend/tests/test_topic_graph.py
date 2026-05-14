import numpy as np

from app.core.config import Settings
from app.services.gpt_service import TopicDraft
from app.services.topic_graph_service import TopicGraphService


class _FakeEmbeddingService:
    def encode(self, texts):
        return np.array(
            [
                [1.0, 0.0],
                [0.95, 0.05],
                [0.9, 0.1],
                [0.85, 0.15],
            ],
            dtype=np.float32,
        )


def test_topic_graph_limits_similarity_neighbors_per_topic():
    service = TopicGraphService(
        Settings(topic_similarity_threshold=0.5, max_similarity_neighbors=1),
        _FakeEmbeddingService(),
    )
    drafts = [
        TopicDraft(title="Topic A", subtopics=[], description="A", difficulty=2, estimated_minutes=60, dependencies=[]),
        TopicDraft(title="Topic B", subtopics=[], description="B", difficulty=2, estimated_minutes=60, dependencies=[]),
        TopicDraft(title="Topic C", subtopics=[], description="C", difficulty=2, estimated_minutes=60, dependencies=[]),
        TopicDraft(title="Topic D", subtopics=[], description="D", difficulty=2, estimated_minutes=60, dependencies=[]),
    ]

    graph = service.build_topic_graph("course-1", drafts)

    assert all(len(topic.similarity_links) <= 2 for topic in graph.topics)
    assert len([edge for edge in graph.edges if edge.edge_type == "similarity"]) <= len(graph.topics)
