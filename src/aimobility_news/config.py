# FEEDS = {
#     "GIM International": "https://www.gim-international.com/rss",
#     "Geospatial World": "https://geospatialworld.net/feed",
#     "Open Geospatial Consortium": "https://www.ogc.org/feed",
#     "QGIS Blog": "https://blog.qgis.org/feed",
#     "Planet OSGeo": "http://planet.osgeo.org/rss20.xml",
#     "Smart Cities Dive": "https://www.smartcitiesdive.com/feeds/news/",
#     "GeoAI signal": "https://testimoniumaltus667974.substack.com/feed/",
#     "GeoAI unpacked" : "https://geoaiunpacked.substack.com/feed/",
#     "GeoAI and law": "https://geospatiallaw.substack.com/feed/", 
#     "Straits Times Singapore": "https://www.straitstimes.com/news/singapore/rss.xml",
#     "Straits Times Business": "https://www.straitstimes.com/news/business/rss.xml",
#     "Business Times Singapore": "https://www.businesstimes.com.sg/rss/singapore",
#     "Business Times Economy & Policy": "https://www.businesstimes.com.sg/rss/economy-policy",
#     "Business Times Telcos Media & Tech": "https://www.businesstimes.com.sg/rss/telcos-media-tech",
#     "Business Times Transport & Logistics": "https://www.businesstimes.com.sg/rss/transport-logistics",
#     "Business Times Startups & Tech": "https://www.businesstimes.com.sg/rss/startups-tech",
#     "Business Times Technology": "https://www.businesstimes.com.sg/rss/technology",
# }

FEEDS = {
    # Specialist transport, autonomous mobility and geospatial publications
    "IEEE Spectrum Full Text": "https://spectrum.ieee.org/rss/fulltext",
    "IEEE Spectrum Robotics": "https://spectrum.ieee.org/rss/blog/automaton/fulltext",
    "Open Geospatial Consortium": "https://www.ogc.org/feed",
    "GeoAI signal": "https://testimoniumaltus667974.substack.com/feed/",
    "GeoAI unpacked" : "https://geoaiunpacked.substack.com/feed/",
    "GeoAI and law": "https://geospatiallaw.substack.com/feed/", 

    # ITS International provides RSS information, but this is not a confirmed feed endpoint
    # "ITS International": "https://www.itsinternational.com/feed/",
}


# Additional AI, Robotics and Mobility RSS feeds
FEEDS_NEW = {
    # Autonomous vehicles and robotics
    "MIT Autonomous Vehicles": "https://news.mit.edu/topic/mitautonomous-vehicles-rss.xml",
    "The Robot Report": "https://www.therobotreport.com/feed/",

    # Industry AI and physical AI
    "NVIDIA Blog": "https://blogs.nvidia.com/feed/",

    # AI research
    "Google Research": "https://research.google/blog/rss/",
    "Google DeepMind": "https://deepmind.google/blog/rss.xml",

    # Broader AI research (optional)
    "Berkeley AI Research": "https://bair.berkeley.edu/blog/feed.xml",
    "Hugging Face Blog": "https://huggingface.co/blog/feed.xml",

    # Category-specific feed (unverified; may overlap)
    # "Robot Report Self Driving": "https://www.therobotreport.com/category/self-driving-vehicles/feed/",
}

FEEDS = FEEDS_NEW

RECENT_HOURS = 72
MIN_TOTAL_SCORE = 3

SCORING_MODEL = "gpt-6.1-sol"

# Cap on full-text words sent to the LLM for scoring
MAX_CONTENT_WORDS = 1500

# A feed summary at least this long is treated as the full article text
FULL_TEXT_MIN_WORDS = 150

# Sources whose feeds carry little or no article text. For recent articles
# from these sources, the article webpage is fetched to get the full text.
PAGE_FETCH_SOURCES = {
    "Google Research",
    "Google DeepMind",
    "Hugging Face Blog",
}

TOP_RANKED = 8