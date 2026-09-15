import os
from datetime import datetime, timezone
from pathlib import Path

from bson.binary import Binary
from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient
from pymongo.errors import PyMongoError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "crimesphere_auth")

if not MONGODB_URI:
    client = None
    db = None
    users_collection = None
    faces_collection = None
    notifications_collection = None
else:
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    db = client[MONGODB_DB_NAME]
    users_collection = db["users"]
    faces_collection = db["face_data"]
    notifications_collection = db["notifications"]

if users_collection is not None:
    users_collection.create_index([("username", ASCENDING)], unique=True)
    users_collection.create_index([("email", ASCENDING)], unique=True, sparse=True)
    users_collection.create_index([("user_id", ASCENDING)], unique=True, sparse=True)
    users_collection.create_index([("role", ASCENDING), ("department", ASCENDING)])
    users_collection.create_index([("status", ASCENDING), ("approval_admin", ASCENDING)])

if faces_collection is not None:
    faces_collection.create_index([("username", ASCENDING)], unique=True)

if notifications_collection is not None:
    notifications_collection.create_index([("admin_username", ASCENDING), ("read", ASCENDING)])


def mongodb_is_available():
    if client is None:
        return False
    try:
        client.admin.command("ping")
        return True
    except PyMongoError:
        return False


def _require_db():
    if users_collection is None or faces_collection is None:
        raise RuntimeError("MongoDB is not configured. Please check your .env file.")


def get_all_users():
    _require_db()
    users = {}
    for document in users_collection.find({}, {"_id": 0}):
        username = str(document.get("username", "")).strip().lower()
        if username:
            document["username"] = username
            users[username] = document
    return users


def get_user(username):
    _require_db()
    return users_collection.find_one({"username": str(username).strip().lower()}, {"_id": 0})


def save_user(username, user_record):
    _require_db()
    clean_username = str(username).strip().lower()
    document = dict(user_record)
    document["username"] = clean_username
    document["updated_at"] = datetime.now(timezone.utc).isoformat()
    users_collection.update_one({"username": clean_username}, {"$set": document}, upsert=True)


def save_users(users):
    for username, record in users.items():
        save_user(username, record)


def save_face(username, face_bytes):
    _require_db()
    clean_username = str(username).strip().lower()
    faces_collection.update_one(
        {"username": clean_username},
        {"$set": {
            "username": clean_username,
            "face_image": Binary(face_bytes),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )


def get_face(username):
    _require_db()
    document = faces_collection.find_one({"username": str(username).strip().lower()})
    if not document or document.get("face_image") is None:
        return None
    return bytes(document["face_image"])


def delete_face(username):
    _require_db()
    faces_collection.delete_one({"username": str(username).strip().lower()})


def create_notification(admin_username, notification_type, message, username):
    _require_db()
    if notifications_collection is None:
        raise RuntimeError("Notifications collection is unavailable.")
    notifications_collection.insert_one({
        "admin_username": str(admin_username).strip().lower(),
        "notification_type": str(notification_type),
        "message": str(message),
        "username": str(username).strip().lower(),
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


def get_notifications(admin_username, unread_only=True):
    _require_db()
    query = {"admin_username": str(admin_username).strip().lower()}
    if unread_only:
        query["read"] = False
    documents = list(notifications_collection.find(query).sort("created_at", -1))
    for document in documents:
        document["notification_id"] = str(document.get("_id", ""))
        document.pop("_id", None)
    return documents


def mark_notification_read(notification_id):
    _require_db()
    from bson import ObjectId
    try:
        notifications_collection.update_one({"_id": ObjectId(notification_id)}, {"$set": {"read": True}})
    except Exception:
        # The UI may pass a string id only when MongoDB returned it; failures are non-fatal.
        return False
    return True


# Compatibility names expected by app.py
def upsert_user(username, user_record):
    return save_user(username, user_record)


def upsert_users(users):
    return save_users(users)


def save_face_image(username, face_bytes):
    return save_face(username, face_bytes)


def get_face_image(username):
    return get_face(username)
