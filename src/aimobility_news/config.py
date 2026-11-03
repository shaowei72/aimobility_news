# ============================================================
# TRANSPORT — Mobility, ITS, autonomous vehicles and rail
# ============================================================

FEEDS_transport = {
    # Tech and transport
    "TechCrunch Transportation": "https://techcrunch.com/category/transportation/feed/",
    "The Verge Transportation": "https://www.theverge.com/rss/transportation/index.xml",
    "Electrek": "https://electrek.co/feed/",

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
    # "Railway-News": "https://railway-news.com/feed/",
    # "Railway Age": "https://www.railwayage.com/feed/",
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


# ============================================================
# CHINESE-LANGUAGE SOURCES (v0.2, section 2.8 of the checkpoint)
# ============================================================
# Scored on the same rubric; reasons, summaries and digest text are written
# in English, and digest titles show the original title with an English
# translation underneath. Text length is measured with textlen.py, which
# counts Chinese characters (1.5 characters = 1 word).

FEEDS_AI_CN = {
    # Leiphone: official category RSS, full text in the feed; the server is
    # slow and the feed is large (1-3.5 MB), see HTTP_TIMEOUT_OVERRIDES
    "Leiphone AI": "https://www.leiphone.com/feed/categoryRss/name/ai",

    # QbitAI: the feed has only the title; full text from the page
    # (PAGE_FETCH_SOURCES)
    "QbitAI": "https://www.qbitai.com/feed",
}

# Tested 2026-11-03, not added (see checkpoint section 2.8):
# "Leiphone Intelligent Driving": "https://www.leiphone.com/feed/categoryRss/name/transportation",  # works on retry; ~2 articles / 72 h
# "Leiphone AI Research": "https://www.leiphone.com/feed/categoryRss/name/academic",                # works on retry; newest 89 h old
# "ITHome": "https://www.ithome.com/rss/",            # ~350 articles / day, mostly consumer tech; needs FEED_KEYWORDS
# "Leiphone Smart Transportation": ".../categoryRss/name/smarttransportation",  # newest entry ~3.6 years old
# "36Kr Articles": "https://36kr.com/feed-article",   # serves an HTML page, not RSS
# "Tropical Geography Remote Sensing GIS": "https://www.rddl.com.cn/CN/rss_lm_2321_1001-5221.xml",  # connection timeout
# "Tropical Geography AI and Geography": "https://www.rddl.com.cn/CN/rss_zt_79_1001-5221.xml",      # HTML error page
# "Acta Geographica GIS": "https://www.geog.com.cn/CN/rss_lm_800_0375-5444.xml",                    # connection timeout


# Sources whose feeds carry little or no article text. For recent articles
# from these sources, the article webpage is fetched and the longer of the
# feed text and the page text is kept.
PAGE_FETCH_SOURCES = {
    "Electrek",
    "The Verge Transportation",
    "TechCrunch Transportation",
    "Google Research",
    "Google DeepMind",
    "Hugging Face Blog",
    "QbitAI",
}

# Keyword pre-filter for high-volume general feeds: an article from a source
# listed here is scored only if its title or text contains one of the
# keywords (case-insensitive). Sources not listed are not filtered.
# Example, for when ITHome is added:
# "ITHome": ["自动驾驶", "智驾", "汽车", "交通", "地铁", "铁路", "公交", "出行",
#            "Robotaxi", "无人驾驶", "地图", "导航", "北斗", "遥感", "测绘", "地理"],
FEED_KEYWORDS: dict[str, list[str]] = {}

# HTTP fetches of feeds and article pages (feeds.http_get): seconds per
# request, and retries on timeouts, connection errors and 5xx responses
HTTP_TIMEOUT = 20
HTTP_TIMEOUT_OVERRIDES = {
    "Leiphone AI": 60,
}
HTTP_RETRIES = 1



# ============================================================
# COMBINED FEEDS — Backward compatibility
# ============================================================

FEEDS = {
    **FEEDS_transport,
    **FEEDS_AI,
    **FEEDS_gis,
    # **FEEDS_AI_CN,               # on hold (checkpoint section 2.8)
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

# SQLite news repository (db.py): runs, articles, every score with the exact
# text the model saw, digest status, AI Daily Brief story sets. Relative to the
# project root. Replaces the v0.3 output/scored-articles.jsonl pool.
DB_FILE = "output/db/news.db"

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

# WhatsApp-ready digest (digest_whatsapp.py): a compact plain-text version of
# the Daily Briefing, written to output/whatsapp-YYYY-MM-DD.txt for manual
# copy/paste. ITS items get a one-line summary (one LLM call for all of
# them); AI Daily Brief items use the story headline.
WHATSAPP_MAX_ITS = 5               # of the up to TOP_RANKED published ITS items
WHATSAPP_MAX_AIDB = 3              # of the up to AIDB_HEADLINES_MAX AI headlines
WHATSAPP_INCLUDE_NOTABLE = True    # include "Also notable" ITS items
WHATSAPP_ONE_LINERS = True         # False: headlines and links only, no LLM call
WHATSAPP_COPY_TO_CLIPBOARD = True  # also put the text on the Windows clipboard

# Cap on full-text words sent to the LLM for scoring
MAX_CONTENT_WORDS = 1500

# A feed summary at least this long is treated as the full article text
FULL_TEXT_MIN_WORDS = 150

