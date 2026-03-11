import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR / 'lp_prospect.db'}"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = "gpt-4o"
OPENAI_TEMPERATURE = 0.2

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TAVILY_MAX_RESULTS = 5

# Rate limiting
TAVILY_CONCURRENT_LIMIT = 5
TAVILY_DELAY_BETWEEN_BATCHES = 1.0
OPENAI_CONCURRENT_LIMIT = 10

# Scoring weights
WEIGHT_SECTOR_FIT = 0.35
WEIGHT_RELATIONSHIP_DEPTH = 0.30
WEIGHT_HALO_VALUE = 0.20
WEIGHT_EMERGING_FIT = 0.15

# Tier thresholds
TIER_PRIORITY_CLOSE = 8.0
TIER_STRONG_FIT = 6.5
TIER_MODERATE_FIT = 5.0

# Check size allocation ranges by org type (low%, high%)
CHECK_SIZE_ALLOCATION = {
    "Pension": (0.005, 0.02),
    "Insurance": (0.005, 0.02),
    "Endowment": (0.01, 0.03),
    "Foundation": (0.01, 0.03),
    "Fund of Funds": (0.02, 0.05),
    "Multi-Family Office": (0.02, 0.05),
    "Single Family Office": (0.03, 0.10),
    "HNWI": (0.03, 0.10),
    "Asset Manager": (0.005, 0.03),
    "RIA/FIA": (0.005, 0.03),
    "Private Capital Firm": (0.005, 0.03),
}

# Cost rates (USD)
COST_TAVILY_PER_SEARCH = 0.01
COST_OPENAI_INPUT_PER_1M = 2.50   # GPT-4o
COST_OPENAI_OUTPUT_PER_1M = 10.00 # GPT-4o

DEFAULT_SCORE = 4
DEFAULT_CONFIDENCE = "Low"
