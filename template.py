import os
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

list_of_files = [
    "localstack/docker-compose.yml",
    "localstack/init/01-create-resources.sh",
    "localstack/init/01-create-resources.sh",
    "poc/__init__.py",
    "poc/aws_clients.py",
    "poc/storage.py",
    "poc/queue_client.py",
    "poc/ingester.py",
    "poc/worker.py",
    "poc/lookup.py",
    "poc/run_pipeline.py",
    "poc/urls.txt",
    "app/__init__.py",
    "app/main.py",        # FastAPI entry point
    "app/fetcher.py",     # Network layer logic
    "app/classifiers/__init__.py",
    "app/classifiers/heuristic.py",   # URL pattern + og:type rules
    "app/classifiers/keybert_topics.py", # KeyBERT keyword extraction
    "app/classifiers/embedding_classifier.py", # MiniLM cosine similarity vs taxonomy
    "app/classifiers/taxonomy.py",    # IAB Tier-1/2 label list
    "app/schemas.py",     # Pydantic models for unified data schema
    "app/config.py",      
    "app/main.py",       
    "app/utils/__init__.py",
    "app/utils/bot_detection.py",  
    "app/utils/logging.py",   
    "app/extractors/__init__.py",
    "app/extractors/trafilatura_layer.py",
    "app/extractors/extruct_layer.py", 
    "app/extractors/bs4_layer.py", 
    "app/extractors/merger.py", 
    "app/orchestrator/__init__.py",
    "app/orchestrator/extractor.py", 
    "app/orchestrator/classifier.py", 
    "scripts/test_fetch.py",
    "scripts/save_fixtures.py",
    "scripts/test_bot_detection.py",
    "scripts/test_extractor.py",
    "scripts/test_classifier.py",
    "tests/fixtures/.gitkeep",
    "docs/DESIGN.md",    
    "docs/POC_PLAN.md",   
    "deploy/Dockerfile",
    ".dockerignore",
    "requirements.txt",
    ".env.example",
    ".gitignore",
    "LICENSE",
    "README.md",
    "images"
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
