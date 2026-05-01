from __future__ import annotations

import os
from functools import lru_cache

from pymongo import MongoClient
from pymongo.collection import Collection


@lru_cache(maxsize=1)
def get_mongo_client() -> MongoClient:
    mongo_uri = os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27017")
    return MongoClient(mongo_uri)


def get_database_name() -> str:
    return os.getenv("MONGODB_DB_NAME", "job_orchestrator")


def get_users_collection() -> Collection:
    db = get_mongo_client()[get_database_name()]
    return db["users"]


def get_job_applications_collection() -> Collection:
    db = get_mongo_client()[get_database_name()]
    return db["job_applications"]


def ensure_mongo_indexes() -> None:
    users = get_users_collection()
    users.create_index("email", unique=True)
    job_applications = get_job_applications_collection()
    job_applications.create_index(
        [("user_id", 1), ("platform", 1), ("job_url", 1)],
        unique=True,
    )
