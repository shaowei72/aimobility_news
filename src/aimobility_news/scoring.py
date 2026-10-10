from .models import Article
from pydantic import BaseModel
from openai import OpenAI
from .feeds import fetch_articles, filter_recent_articles, deduplicate_articles
from .ranking import rank_articles
from .digest import generate_digest, save_digest
from .config import SCORING_MODEL

client = OpenAI()

class ArticleScore(BaseModel):
    ai_score: int
    geoai_score: int
    transport_score: int

def score_article(article: Article) -> Article:
    prompt = f"""
        Evaluate the relevance of this news article.

        Score each criterion as integers from 1 to 5:

        - ai_score:
        How relevant is this article to artificial intelligence?

        - geoai_score:
        How relevant is this article to GIS, geospatial technology,
        spatial analytics, mapping, digital twins, or GeoAI?

        - transport_score:
        How relevant is this article to land transport, including
        roads, rail, buses, traffic management, mobility, transport
        planning, or transport operations?

        The scoring rubric for each of the ai_score, geoai_score and transport_score is:

        1 = not relevant or weakly/indirectly relevant
        2 = somewhat relevant
        3 = clearly relevant
        4 = highly relevant
        5 = central to the article

        Article title:
        {article.title}

        Article summary:
        {article.summary}
        """

    response = client.responses.parse(
        model=SCORING_MODEL,
        input=prompt,
        text_format=ArticleScore,
    )

    scores = response.output_parsed

    article.ai_score = scores.ai_score
    article.geoai_score = scores.geoai_score
    article.transport_score = scores.transport_score

    article.total_score = (
        article.ai_score*article.geoai_score *article.transport_score
    )

    return article

def score_articles(articles: list[Article]) -> list[Article]:
    scored_articles = []

    for article in articles:
        scored_article = score_article(article)
        scored_articles.append(scored_article)

    return scored_articles


if __name__ == "__main__":
    articles = fetch_articles()
    recent_articles = filter_recent_articles(articles)
    unique_articles = deduplicate_articles(recent_articles)
    scored_articles = score_articles(unique_articles)
    ranked_articles = rank_articles(scored_articles)

    # for article in ranked_articles:
    #     print("\n")
    #     print(article.title)
        # print(f"AI score: {scored.ai_score}")
        # print(f"GeoAI score: {scored.geoai_score}")
        # print(f"Transport score: {scored.transport_score}")
    #     print(f"Total score: {article.total_score}")

    top_5 = ranked_articles[:5]
    digest = generate_digest(top_5)
    file_path = save_digest(digest)
    print(f"Digest saved to: {file_path}")
    
    print(digest)


    # test_article = Article(
    #     title="PwC and Esri to harness geospatial AI together",
    #     url="https://example.com/article",
    #     source="GIM International",
    #     published_at=None,
    #     summary="PwC and Esri announced a collaboration involving geospatial AI."
    # )

    # scored_article = score_article(test_article)

    # print(scored_article.title)
    # print(f"AI score: {scored_article.ai_score}")
    # print(f"GeoAI score: {scored_article.geoai_score}")
    # print(f"Transport score: {scored_article.transport_score}")
    # print(f"Total score: {scored_article.total_score}")

    # articles = [
    #     Article(
    #         title="Article 1",
    #         url="https://example.com/1",
    #         source="Source A",
    #         published_at=None,
    #         summary=None
    #     ),
    #     Article(
    #         title="Article 2",
    #         url="https://example.com/2",
    #         source="Source B",
    #         published_at=None,
    #         summary=None
    #     ),
    # ]
    
    # scored_articles = score_articles(articles)
    # print(len(scored_articles))

    # for article in scored_articles:
    #     print(f"Title: {article.title}, Total AI score: {article.total_score}")