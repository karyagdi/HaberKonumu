# app/db/mongo.py

import os
from pathlib import Path

from pymongo import MongoClient
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "news_db")
COLLECTION_NAME = "news"


def get_database():
    if not MONGO_URI:
        raise ValueError("MONGO_URI .env dosyasinda tanimli degil")

    client = MongoClient(MONGO_URI)
    return client[DB_NAME]


def get_news_collection():
    db = get_database()
    return db[COLLECTION_NAME]