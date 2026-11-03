from .models import Article
from pydantic import BaseModel, Field
from . import llm
from .config import MAX_CONTENT_WORDS
from .textlen import truncate_text

# Reasons come before scores so the model explains first, then scores.
# Field order follows the prompt: transport, AI, GIS.
# Scores are bounded 0-5: Ollama and OpenAI receive the bounds in the JSON
# schema, and Pydantic rejects anything outside them (which triggers a retry).
class ArticleScore(BaseModel):
    transport_reason: str
    transport_score: int = Field(ge=0, le=5)
    ai_reason: str
    ai_score: int = Field(ge=0, le=5)
    gis_reason: str
    gis_score: int = Field(ge=0, le=5)

def text_for_scoring(article: Article) -> tuple[str, str | None]:
    # Prefer the full article text when the feed provides it, capped for cost.
    # The cap is in English-word equivalents, so Chinese text is capped at
    # about the same amount of content (textlen.py).
    if article.content:
        return "Article full text", truncate_text(article.content, MAX_CONTENT_WORDS)
    return "Article summary", article.summary


def combine_scores(transport: int, ai: int, gis: int) -> int:
    # (transport + 1) x (ai + gis + 1) - 1, range 0-65. Equivalent to
    # transport + ai + gis + transport x (ai + gis): each domain adds a little
    # on its own (at most 5, or 10 for AI + GIS without transport), and
    # transport combined with AI and/or GIS multiplies.
    return (transport + 1) * (ai + gis + 1) - 1


def score_article(article: Article) -> Article:
    text_label, text = text_for_scoring(article)

    prompt = f"""
Evaluate the relevance and significance of this news article for a
daily briefing covering three domains:

1. Land Transport
2. Artificial Intelligence (AI)
3. Geographic Information Systems (GIS) and GeoAI

Score each domain independently, using an integer from 0 to 5.
Provide a one-sentence reason explaining each score.

The objective is to identify substantive news, technological
developments, operational deployments, research breakthroughs,
and policy developments relevant to these domains.

An article does not need to cover more than one domain to
receive a high score.

------------------------------------------------------------
1. LAND TRANSPORT RELEVANCE (transport_score)
------------------------------------------------------------

Assess the relevance and significance of the article to
land transport, with particular interest in Singapore,
intelligent transport systems (ITS), transport operations,
technology adoption, infrastructure and policy.

Land transport includes:
- Road networks, traffic operations and traffic management
- Rail, MRT, LRT and railway systems
- Buses, taxis, ride-hailing and public transport
- Autonomous vehicles and connected vehicles
- Cycling, walking and micromobility
- Land freight, trucking and logistics
- Transport planning, infrastructure and regulation
- Transport safety, enforcement and sustainability
- Transport data, digital platforms and intelligent systems

Aviation and maritime are excluded unless the article
substantially concerns their land-side transport connections.

Scoring rubric:

0 = No meaningful connection to land transport.

1 = Land transport is mentioned only incidentally,
    without substantive transport information.

2 = Routine or general transport news with limited
    strategic, technological, operational or policy relevance.
    Examples: individual accidents, routine vehicle launches,
    minor fare announcements, company earnings or appointments.

3 = Substantive transport development involving planning,
    operations, infrastructure, policy or technology.
    Examples: new rail maintenance programmes, fleet
    electrification strategies, public transport reforms,
    mobility platforms or significant ridership developments.

4 = Significant transport innovation, operational deployment,
    policy change or technology advancement.
    Examples: AI-enabled traffic control, autonomous bus
    trials, predictive rail maintenance, major ITS deployments,
    integrated mobility platforms or network optimisation.

5 = Highly consequential transport development with major
    implications for transport operations, technology,
    policy, safety or future mobility.
    Examples: large-scale autonomous vehicle deployment,
    transformative traffic management systems, major
    intelligent transport initiatives, significant regulatory
    changes or breakthrough transport technologies.

Singapore relevance:
- Give particular consideration to developments directly
  affecting Singapore's land transport ecosystem.
- International developments can score equally highly
  if their significance warrants it.
- Geographic proximity alone does not justify a high score.


------------------------------------------------------------
2. ARTIFICIAL INTELLIGENCE RELEVANCE (ai_score)
------------------------------------------------------------

Assess the relevance and significance of the article to
artificial intelligence technology, research, applications,
deployment, governance and industry transformation.

Particular interests include:
- Foundation models, LLMs and multimodal AI
- Agentic AI and autonomous systems
- Robotics, physical AI and embodied intelligence
- Computer vision and perception systems
- AI reasoning, planning and decision-making
- AI for science and engineering
- AI applications in industry and enterprise productivity
- AI in transport and infrastructure operations
- AI safety, security, governance and responsible AI
- AI platforms, infrastructure and deployment engineering

Scoring rubric:

0 = No meaningful AI content.

1 = AI is mentioned only incidentally or as a marketing
    buzzword, without explaining the technology or application.

2 = General AI news with some substance but limited technical
    or application significance.
    Examples: routine funding announcements, company
    announcements, broad AI adoption trends or incremental
    product updates.

3 = Substantive AI technology development or concrete
    application with identifiable capabilities or benefits.
    Examples: enterprise AI agents, predictive maintenance
    models, AI-driven business processes, new model
    capabilities or practical computer vision applications.

4 = Significant AI advancement, innovative application or
    operational deployment with meaningful implications.
    Examples: important advances in model capabilities,
    agentic automation, robotics intelligence, industrial AI,
    AI safety engineering or large-scale AI adoption.

5 = Highly consequential AI development, major breakthrough
    or transformative deployment with broad technological,
    industrial or operational implications.
    Examples: major advances in AI architectures, reasoning
    or autonomy; important foundation model innovations;
    transformative AI deployments; or landmark AI safety
    and governance developments.

AI relevance is assessed independently of transport and GIS.
An important AI development can score 5 even when it has
no transport or geospatial application.


------------------------------------------------------------
3. GIS AND GEOAI RELEVANCE (gis_score)
------------------------------------------------------------

Assess the relevance and significance of the article to
geographic information systems, geospatial technologies,
spatial data, location intelligence and GeoAI.

GIS and geospatial technology include:
- GIS platforms, tools and spatial analytics
- Geospatial data infrastructure and standards
- Satellite, aerial and street-level imagery
- Remote sensing and earth observation
- LiDAR, point clouds and 3D spatial modelling
- GNSS, GPS, positioning and navigation
- Location intelligence and trajectory analytics
- Digital twins with meaningful geospatial components
- Spatial databases, spatial computing and mapping
- Geospatial foundation models and GeoAI
- AI applied to imagery, maps, trajectories and spatial data
- Geospatial applications in transport, cities,
  infrastructure, environment and public services

Scoring rubric:

0 = No meaningful GIS or geospatial content.

1 = Geographic location, maps or spatial data are mentioned
    only incidentally, without substantive geospatial content.

2 = General GIS or geospatial news with limited technical
    or application significance.
    Examples: routine map updates, minor product releases,
    general satellite announcements or industry news.

3 = Substantive GIS technology development, spatial analytics
    application or geospatial deployment.
    Examples: new spatial datasets, remote sensing applications,
    GIS-enabled planning, location analytics or operational
    mapping platforms.

4 = Significant GIS or GeoAI advancement, innovative spatial
    technology or consequential operational deployment.
    Examples: advanced geospatial analytics, 3D city models,
    digital twin deployments, AI-enhanced remote sensing,
    major GIS platform innovations or geospatial data
    infrastructure developments.

5 = Highly consequential GIS or GeoAI innovation, breakthrough
    or transformative deployment with major implications
    for spatial intelligence or geospatial technology.
    Examples: geospatial foundation models, breakthrough
    spatial AI methods, major geospatial platform advances,
    transformative spatial digital twins or significant
    geospatial data infrastructure innovations.

GIS relevance does not require AI or transport content.
An important conventional GIS development can score 5
even when no AI technology is involved.


------------------------------------------------------------
GENERAL SCORING RULES
------------------------------------------------------------

1. Score each of the three domains independently.

2. Do not require overlap between domains.
   An article may score 5 in one domain and 0 in the others.

3. Assess both topical relevance and the significance
   of the development within each domain.

4. Score only information supported by the article.
   Do not infer AI, GIS or transport capabilities that
   are not described.

5. Judge the article's main subject, not isolated keywords
   or passing mentions.

6. A concrete operational deployment or significant applied
   innovation may score as highly as a research breakthrough.

7. Do not reward marketing language such as "AI-powered",
   "smart", "next-generation" or "revolutionary" unless
   supported by substantive details.

8. If an article sits between two scoring levels,
   choose the lower score.

9. When the article contains insufficient information,
   score conservatively rather than inventing details.

10. Singapore relevance is important for Transport,
    but international developments should be assessed
    on their own significance and potential applicability.

11. Avoid inflating scores simply because an article
    originates from a specialist publisher.

12. Provide a concise, evidence-based, one-sentence
    explanation for each domain score.

13. The article may be in another language (e.g. Chinese).
    Score it on the same basis, and always write the
    explanations in English.

Return the three scores and their explanations using
the existing structured output schema.


Article title:
{article.title}

{text_label}:
{text}
"""

    scores = llm.parse(
        prompt, ArticleScore, task="scoring", label=article.title
    )
    article.scored_by = llm.describe("scoring")

    article.transport_score = scores.transport_score
    article.transport_reason = scores.transport_reason
    article.ai_score = scores.ai_score
    article.ai_reason = scores.ai_reason
    article.gis_score = scores.gis_score
    article.gis_reason = scores.gis_reason

    article.total_score = combine_scores(
        article.transport_score, article.ai_score, article.gis_score
    )

    return article

def score_articles(articles: list[Article]) -> list[Article]:
    # One article failing (invalid output after retries, timeout, HTTP error)
    # is recorded on the article and the run continues. If every article
    # fails, the provider itself is probably down, so stop.
    scored_articles = []
    failures = 0

    for article in articles:
        try:
            scored_article = score_article(article)
        except Exception as e:
            failures += 1
            article.scored_by = llm.describe("scoring")
            article.scoring_error = f"{type(e).__name__}: {e}"
            print(f"WARNING: scoring failed for {article.title!r}: {article.scoring_error}")
            scored_article = article
        scored_articles.append(scored_article)

    if articles and failures == len(articles):
        raise RuntimeError(
            f"Scoring failed for all {failures} articles; last error: "
            f"{scored_articles[-1].scoring_error}"
        )

    if failures:
        print(f"Scoring failed for {failures} of {len(articles)} articles")

    return scored_articles


if __name__ == "__main__":
    import sys

    # Optional provider override: python -m aimobility_news.scoring ollama
    if len(sys.argv) > 1:
        llm.set_provider(sys.argv[1])

    test_article = Article(
        title="PwC and Esri to harness geospatial AI together",
        url="https://example.com/article",
        source="GIM International",
        published_at=None,
        summary="PwC and Esri announced a collaboration involving geospatial AI."
    )

    scored_article = score_article(test_article)

    print(f"Scored by: {scored_article.scored_by}")
    print(scored_article.title)
    print(
        f"Transport score: {scored_article.transport_score} — "
        f"{scored_article.transport_reason}"
    )
    print(f"AI score: {scored_article.ai_score} — {scored_article.ai_reason}")
    print(f"GIS score: {scored_article.gis_score} — {scored_article.gis_reason}")
    print(f"Total score: {scored_article.total_score}")
