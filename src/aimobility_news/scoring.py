from .models import Article
from pydantic import BaseModel
from openai import OpenAI
from .config import SCORING_MODEL, MAX_CONTENT_WORDS

client = OpenAI()

# Reasons come before scores so the model explains first, then scores.
class ArticleScore(BaseModel):
    ai_reason: str
    ai_score: int
    transport_reason: str
    transport_score: int

def text_for_scoring(article: Article) -> tuple[str, str | None]:
    # Prefer the full article text when the feed provides it, capped for cost
    if article.content:
        words = article.content.split()
        return "Article full text", " ".join(words[:MAX_CONTENT_WORDS])
    return "Article summary", article.summary


def score_article(article: Article) -> Article:
    text_label, text = text_for_scoring(article)

    prompt = f"""
        Evaluate the relevance of this news article for a daily briefing on
        AI and GeoAI applied to land transport.

        Score each criterion as an integer from 0 to 5, and give a
        one-sentence reason for each score.

        - ai_score:
        How relevant is this article to artificial intelligence, with emphasis
        on GeoAI: AI applied to spatial or location data, such as satellite,
        aerial or street-level imagery, LiDAR and point clouds, GPS and
        movement trajectories, road and map networks, digital twins, and GIS
        platforms?

        - transport_score:
        How relevant is this article to land transport, with emphasis on the
        use of GIS and geospatial data in transport: road and rail networks,
        transit routes and stops, traffic and movement data, transport assets
        and infrastructure as mapped, located or spatially analysed?

        Land transport covers roads, rail, MRT/LRT, buses, taxis and
        ride-hailing, cycling, walking, micromobility, and land freight and
        logistics. Aviation and maritime are out of scope unless the article
        concerns their land-side connections.

        The scoring rubric for the ai_score is as follows:
        0 = No AI content.
        1 = AI is mentioned only in passing or as a buzzword (e.g. "AI-powered"
            with no detail about what the AI does).
        2 = General AI news with substance but no concrete application: models,
            chips, funding, acquisitions, regulation, AI company strategy.
        3 = A concrete AI application or deployment that does not rely on spatial
            data: e.g. chatbots, predictive maintenance from sensor logs, demand
            forecasting from ticketing data, AI for document processing.
        4 = AI applied to spatial or location data is a significant part of the
            article: e.g. computer vision on road or traffic camera imagery,
            trajectory or GPS analytics, AI-based mapping, location-aware
            prediction (where and when congestion or incidents will occur).
        5 = GeoAI is the central subject: a new GeoAI method, model, dataset,
            product or deployment; geospatial foundation models; AI features in
            GIS platforms (e.g. ArcGIS, QGIS); AI extraction of features from
            imagery or point clouds.

        The scoring rubric for the transport_score is as follows:
        0 = No land transport content.
        1 = Transport is mentioned only in passing (e.g. a company that also has
            logistics customers, a commute mentioned in a lifestyle story).
        2 = Transport is the subject, but the news is routine and has no planning,
            operational or policy substance: individual accidents, fare changes,
            vehicle launches, transport company earnings or appointments.
        3 = Substantive land transport planning, operations, policy,
            infrastructure or technology, without a meaningful spatial element:
            e.g. rail maintenance programmes, fleet electrification policy,
            ticketing systems, ridership trends, transport regulation.
        4 = Spatial or location data is a significant part of the transport
            story: e.g. route or network planning using maps, GPS fleet or vehicle
            tracking, traffic flow or congestion by location, accessibility or
            catchment analysis, siting of stations, depots or EV chargers, road
            asset inventories.
        5 = GIS or geospatial technology for transport is the central subject:
            e.g. transport GIS platforms, mapping or digital twins of road or rail
            networks, HD maps for vehicles, spatial analytics for network or land
            use–transport planning, mobility data standards (e.g. GTFS, OGC).

        General rules:
        - Score only what the title and article text actually say. Do not infer
          AI, spatial or transport content that is not stated, even if the
          technology plausibly involves it.
        - Score each criterion independently. An article can be high on
          both, high on one and 0 on the other, or 0 on both.
        - If an article sits between two levels, choose the lower one.
        - If the article text is missing or very short, score from the
          title alone and be conservative.
        - When the full article text is given, score on its main subject;
          a passing mention in a long article does not raise a score.
        - Marketing language ("smart", "AI-powered", "next-generation")
          without detail does not raise a score above 1.

        Borderline guidance for ai_score:
        - "Algorithms", "analytics", "automation", "sensors" or "data-driven"
          are not AI unless machine learning, AI models or AI-based
          prediction or detection are explicitly described.
        - Conventional traffic simulation or optimisation models without
          AI: 0–1.
        - GeoAI with no transport content (e.g. agriculture, forestry,
          land use, disaster mapping) still scores 4–5 on ai_score; the
          transport criterion handles relevance to transport.
        - Digital twins: 4–5 only if AI is actually used; a digital twin
          without AI is 1 at most.
        - AI regulation or policy specific to transport (e.g. autonomous
          vehicle laws): 2.
        - Newsletters or round-ups covering many topics: score only what
          is described in the article text; a single item among many unrelated
          ones scores no higher than 2.

        Borderline guidance for transport_score:
        - Autonomous vehicles: 3 for trials, regulation or business news;
          4–5 if the focus is mapping, localisation, or operating areas and
          routes.
        - EVs: a vehicle launch is 2; charging policy is 3; spatial
          planning of a charging network is 4.
        - Ride-hailing and navigation apps: business or pricing news is 2;
          matching or dispatch operations is 3; routing, ETA prediction or
          map features is 4–5.
        - Freight and logistics: road or rail freight operations count as
          land transport; warehouse-only operations, e-commerce or supply
          chain finance score 1 at most.
        - Delivery drones, aviation and maritime: 0, unless the article
          concerns their land-side connections (e.g. airport rail links,
          port-to-road freight), which score up to 3.
        - Smart city stories: score only the land transport content, not
          the smart city framing.
        - Property, land or urban development: 0–1 unless transport access,
          stations or networks are a substantive part of the story.
        - Disasters or weather (e.g. floods, landslides): 3–4 only if
          impacts on roads, rail or transport operations are discussed.

        Article title:
        {article.title}

        {text_label}:
        {text}
        """

    response = client.responses.parse(
        model=SCORING_MODEL,
        input=prompt,
        text_format=ArticleScore,
    )

    scores = response.output_parsed

    article.ai_score = scores.ai_score
    article.ai_reason = scores.ai_reason
    article.transport_score = scores.transport_score
    article.transport_reason = scores.transport_reason

    # Product: an article must be relevant to both AI and land transport.
    article.total_score = article.ai_score * article.transport_score

    return article

def score_articles(articles: list[Article]) -> list[Article]:
    scored_articles = []

    for article in articles:
        scored_article = score_article(article)
        scored_articles.append(scored_article)

    return scored_articles


if __name__ == "__main__":
    test_article = Article(
        title="PwC and Esri to harness geospatial AI together",
        url="https://example.com/article",
        source="GIM International",
        published_at=None,
        summary="PwC and Esri announced a collaboration involving geospatial AI."
    )

    scored_article = score_article(test_article)

    print(scored_article.title)
    print(f"AI score: {scored_article.ai_score} — {scored_article.ai_reason}")
    print(
        f"Transport score: {scored_article.transport_score} — "
        f"{scored_article.transport_reason}"
    )
    print(f"Total score: {scored_article.total_score}")
