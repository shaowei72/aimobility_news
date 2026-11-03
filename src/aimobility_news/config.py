# ============================================================
# TRANSPORT — Mobility, ITS, autonomous vehicles and rail
# ============================================================

FEEDS_transport = {
    # Techcrunch
    "TechCrunch Transportation": "https://techcrunch.com/category/transportation/feed/",

    # Autonomous vehicles and mobility
    "MIT Autonomous Vehicles": "https://news.mit.edu/topic/mitautonomous-vehicles-rss.xml",
    "InsideEVs Autonomous Vehicles": "https://insideevs.com/rss/category/autonomous-vehicles/",
    "ADAS Autonomous Vehicle International": "https://www.autonomousvehicleinternational.com/feed/",

    # Robotics and autonomous systems
    # "The Robot Report": "https://www.therobotreport.com/feed/",
    "IEEE Spectrum Robotics": "https://spectrum.ieee.org/rss/blog/automaton/fulltext",

    # Transport operations and smart cities
    "TransportXtra Technology": "https://www.transportxtra.com/rss/?id=44",
    "TransportXtra Passenger Technology": "https://www.transportxtra.com/rss/?id=30",
    "Smart Cities Dive": "https://www.smartcitiesdive.com/feeds/news/",

    # Automotive technology
    "Tech Xplore Automotive": "https://techxplore.com/rss-feed/automotive-news/",

    # Railway technology and operations
    "Railway-News": "https://railway-news.com/feed/",
    "Railway Age": "https://www.railwayage.com/feed/",

    # Additional transport feeds to test
    # "TechCrunch Transportation": "https://techcrunch.com/category/transportation/feed/",
    # "The Verge Transportation": "https://www.theverge.com/rss/transportation/index.xml",
    # "Electrek": "https://electrek.co/feed/",
    # "Transport Topics": "https://www.ttnews.com/rss.xml",

    # RSS endpoint previously returning HTTP 403
    # "ITS International": "https://www.itsinternational.com/feed/",
}

# ============================================================
# AI — AI research, robotics and physical AI
# ============================================================

FEEDS_AI = {
    # General AI and engineering
    "IEEE Spectrum Full Text": "https://spectrum.ieee.org/rss/fulltext",
    "NVIDIA Blog": "https://blogs.nvidia.com/feed/",

    # AI research
    "Google Research": "https://research.google/blog/rss/",
    "Google DeepMind": "https://deepmind.google/blog/rss.xml",
    "Berkeley AI Research": "https://bair.berkeley.edu/blog/feed.xml",
    "Hugging Face Blog": "https://huggingface.co/blog/feed.xml",

    # Applied AI and robotics
    "Tech Xplore Robotics": "https://techxplore.com/rss-feed/robotics-news/",
    "Tech Xplore AI": "https://techxplore.com/rss-feed/machine-learning-ai-news/",
    "NVIDIA Developer Robotics": "https://developer.nvidia.com/blog/category/robotics/feed/",
    "InsideEVs Artificial Intelligence": "https://insideevs.com/rss/category/artificial-intelligence/",
}


# ============================================================
# GIS — Geospatial technology, GeoAI and spatial analytics
# ============================================================

FEEDS_gis = {
    # Geospatial standards and infrastructure
    "Open Geospatial Consortium": "https://www.ogc.org/feed",

    # GeoAI publications
    "GeoAI signal": "https://testimoniumaltus667974.substack.com/feed/",
    "GeoAI unpacked": "https://geoaiunpacked.substack.com/feed/",
    "GeoAI and law": "https://geospatiallaw.substack.com/feed/",

}


# Sources whose feeds carry little or no article text. For recent articles
# from these sources, the article webpage is fetched to get the full text.
PAGE_FETCH_SOURCES = {
    "Google Research",
    "Google DeepMind",
    "Hugging Face Blog",
}



# ============================================================
# COMBINED FEEDS — Backward compatibility
# ============================================================

FEEDS = {
    **FEEDS_transport,
    **FEEDS_AI,
    **FEEDS_gis,
}

RECENT_HOURS = 24
# total = (transport + 1) x (ai + gis + 1) - 1, range 0-65 (see scoring.py).
# 11 = some transport link plus AI/GIS, e.g. T2 + A3, T3 + A2; nothing without
# transport passes (max 10). 15 = T3 + A3, roughly the old 9 on AI x transport.
MIN_TOTAL_SCORE = 11

# Articles below MIN_TOTAL_SCORE that reach any one of these scores on its own
# are "notable" and published under "Also notable", after the qualified
# articles, within TOP_RANKED. Set a value above 5 to disable that domain.
# Rubric levels: 2 = routine/general news, 3 = substantive development,
# 4 = significant advance or deployment, 5 = highly consequential.
NOTABLE_MIN_TRANSPORT_SCORE = 3
NOTABLE_MIN_AI_SCORE = 3
NOTABLE_MIN_GIS_SCORE = 3


TOP_RANKED = 8

# ------------------------------------------------------------
# LLM provider (see llm.py). main.py --provider overrides LLM_PROVIDER.
# ------------------------------------------------------------
LLM_PROVIDER = "openai"            # "openai" or "ollama"

OPENAI_MODEL = "gpt-6.1-sol"       # also used by Esri search (web search)

# Tasks: scoring, digest, transcript (AI Daily Brief story grouping and
# summaries, aidailybrief_transcript.py) and judge (its optional comparison).
LLM_MODELS = {
    "openai": {
        "scoring": OPENAI_MODEL,
        "digest": OPENAI_MODEL,
        "transcript": OPENAI_MODEL,
        "judge": OPENAI_MODEL,
    },
    "ollama": {
        "scoring": "qwen3.5:9b",
        "digest": "qwen3.5:9b",
        "transcript": "qwen3.5:9b",
        "judge": "qwen3.5:9b",
    },
}

OLLAMA_HOST = "http://localhost:11434"
# Scoring prompt is ~2,500 tokens of rubric + up to MAX_CONTENT_WORDS of text.
# Too small a context silently truncates the prompt.
OLLAMA_NUM_CTX = 16384
OLLAMA_TEMPERATURE = 0
OLLAMA_THINK = False               # True / False for thinking models; None = model default
OLLAMA_TIMEOUT = 300               # seconds per call
OLLAMA_MAX_ATTEMPTS = 2            # retries when the output fails schema validation

# One CSV row per LLM call (tokens, timing, status), appended across runs.
# Relative to the project root; set to None to disable.
LLM_CALL_LOG = "output/llm-calls.csv"

# Every run appends its scored articles (text, scores, reasons) here, one JSON
# object per line: the pool the evaluation dataset is picked from.
# Relative to the project root; set to None to disable.
SCORED_POOL = "output/scored-articles.jsonl"

# AI Daily Brief stories (aidailybrief_transcript.py). Each episode's source
# files and LLM outputs go to <AIDB_DIR>/<date>/ (relative to the project root).
AIDB_DIR = "output/aidailybrief"
# Transcript markers are whole minutes and a heading's minute is only roughly
# where its story starts, so each story's excerpt is widened by this many
# minutes before its first heading and after its last heading's minute.
AIDB_BUFFER_BEFORE_MIN = 1
AIDB_BUFFER_AFTER_MIN = 1

# AI Daily Brief is the backbone AI source: each recent episode is split into
# stories, which are scored like any article. A story that qualifies on the
# total score goes in the main digest as usual. Otherwise, if its AI score
# reaches AIDB_HEADLINES_MIN_AI_SCORE, it is an "AI headline": published in a
# separate "AI Daily Brief" digest section, highest AI score first, up to
# AIDB_HEADLINES_MAX, so it never takes one of the TOP_RANKED slots.
AIDB_SOURCE = "AI Daily Brief"
AIDB_HEADLINES_MAX = 4
AIDB_HEADLINES_MIN_AI_SCORE = 3

# Cap on full-text words sent to the LLM for scoring
MAX_CONTENT_WORDS = 1500

# A feed summary at least this long is treated as the full article text
FULL_TEXT_MIN_WORDS = 150

