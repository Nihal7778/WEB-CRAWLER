from app.schemas import CrawlResponse, CrawlStatus, Topic, TopicSource

r = CrawlResponse(
    url="https://example.com",
    requested_url="https://example.com",
    status=CrawlStatus.SUCCESS,
    topics=[Topic(topic="news", confidence=0.9, source=TopicSource.EMBEDDING)],
)
print(r.model_dump_json(indent=2))