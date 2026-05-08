import os
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

list_of_files = [
    "app/__init__.py",
    "app/main.py",        # FastAPI entry point
    "app/fetcher.py",     # Network layer logic
    "app/classifiers/__init__.py",
    "app/classifiers/heuristic.py",   # URL pattern + og:type rules
    "app/classifiers/keybert_topics.py", # KeyBERT keyword extraction
    "app/classifiers/embedding_classifier.py", # MiniLM cosine similarity vs taxonomy
    "app/classifiers/taxonomy.py",    # IAB Tier-1/2 label list
    "app/schemas.py",     # Pydantic models for unified data schema
    "app/config.py",      # Environment variables & constants
    "app/main.py",       # FastAPI entry point
    "app/utils/__init__.py",
    "app/utils/bot_detection.py",  # Bot detection logic
    "app/utils/logging.py",     # Custom logging setup
    "app/extractors/__init__.py",
    "app/extractors/trafilatura_layer.py",# Primary: title, body, author, date
    "app/extractors/extruct_layer.py", #OG, Twitter, JSON-LD
    "app/extractors/bs4_layer.py", #Fallback for missing meta tags
    "app/extractors/merger.py", #Combines outputs from all layers
    "app/orchestrator/__init__.py",
    "app/orchestrator/extractor.py", # Metadata extraction logic
    "app/orchestrator/classifier.py", # Classification & Topic logic
    "scripts/test_fetch.py",
    "scripts/save_fixtures.py",
    "scripts/test_bot_detection.py",
    "scripts/test_extractor.py",
    "scripts/test_classifier.py",
    "tests/fixtures/.gitkeep",
    "docs/DESIGN.md",     # Part 2 requirement
    "docs/POC_PLAN.md",   # Part 3 requirement
    "deploy/Dockerfile",
    ".dockerignore",
    "requirements.txt",
    ".env.example",
    ".gitignore",
    "LICENSE",
    "README.md"
]

for file_path in list_of_files:
    filepath = Path(file_path)
    filedir, filename = os.path.split(filepath)

    # Create directory if it doesn't exist
    if filedir != "":
        os.makedirs(filedir, exist_ok=True)
        logging.info(f"Created directory: {filedir} for file: {filename}")

    # Create empty file if it doesn't exist or is empty
    if not filepath.exists() or filepath.stat().st_size == 0:
        with open(filepath, "w") as f:
            pass
        logging.info(f"Created empty file: {filepath}")
    else:
        logging.info(f"{filename} already exists")
