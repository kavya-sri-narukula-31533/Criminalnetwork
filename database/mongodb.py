import os
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING
from pymongo.errors import PyMongoError
from bson.binary import Binary


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]


# ============================================================
# LOAD .ENV
# ============================================================

load_dotenv(PROJECT_ROOT / ".env")


MONGODB_URI = os.getenv("MONGODB_URI")

MONGODB_DB_NAME = os.getenv(
    "MONGODB_DB_NAME",
    "crimesphere_auth"
)


# ============================================================
# MONGODB CONNECTION
# ============================================================

if not MONGODB_URI:

    client = None
    db = None
    users_collection = None
    faces_collection = None

else:

    client = MongoClient(
        MONGODB_URI,
        serverSelectionTimeoutMS=5000
    )

    db = client[MONGODB_DB_NAME]

    users_collection = db["users"]

    faces_collection = db["face_data"]


# ============================================================
# CREATE INDEXES
# ============================================================

if users_collection is not None:

    users_collection.create_index(
        [("username", ASCENDING)],
        unique=True
    )

    users_collection.create_index(
        [("email", ASCENDING)],
        unique=True,
        sparse=True
    )

    users_collection.create_index(
        [("user_id", ASCENDING)],
        unique=True,
        sparse=True
    )


if faces_collection is not None:

    faces_collection.create_index(
        [("username", ASCENDING)],
        unique=True
    )


# ============================================================
# TEST MONGODB CONNECTION
# ============================================================

def mongodb_is_available():

    if client is None:
        return False

    try:

        client.admin.command("ping")

        return True

    except PyMongoError:

        return False


# ============================================================
# REQUIRE DATABASE
# ============================================================

def _require_db():

    if (
        users_collection is None
        or faces_collection is None
    ):

        raise RuntimeError(
            "MongoDB is not configured. "
            "Please check your .env file."
        )


# ============================================================
# GET ALL USERS
# ============================================================

def get_all_users():

    _require_db()

    users = {}

    documents = users_collection.find(
        {},
        {"_id": 0}
    )

    for document in documents:

        username = str(
            document.get("username", "")
        ).strip().lower()

        if username:

            document["username"] = username

            users[username] = document

    return users


# ============================================================
# GET ONE USER
# ============================================================

def get_user(username):

    _require_db()

    clean_username = str(
        username
    ).strip().lower()

    return users_collection.find_one(
        {
            "username": clean_username
        },
        {
            "_id": 0
        }
    )


# ============================================================
# SAVE / UPDATE ONE USER
# ============================================================

def save_user(username, user_record):

    _require_db()

    clean_username = str(
        username
    ).strip().lower()

    document = dict(user_record)

    document["username"] = clean_username

    document["updated_at"] = (
        datetime.now(timezone.utc).isoformat()
    )

    users_collection.update_one(

        {
            "username": clean_username
        },

        {
            "$set": document
        },

        upsert=True
    )


# ============================================================
# SAVE / UPDATE ALL USERS
# ============================================================

def save_users(users):

    _require_db()

    for username, record in users.items():

        save_user(
            username,
            record
        )


# ============================================================
# SAVE FACE IMAGE
# ============================================================

def save_face(username, face_bytes):

    _require_db()

    clean_username = str(
        username
    ).strip().lower()

    faces_collection.update_one(

        {
            "username": clean_username
        },

        {
            "$set": {

                "username": clean_username,

                "face_image": Binary(
                    face_bytes
                ),

                "updated_at": (
                    datetime.now(
                        timezone.utc
                    ).isoformat()
                )
            }
        },

        upsert=True
    )


# ============================================================
# GET FACE IMAGE
# ============================================================

def get_face(username):

    _require_db()

    clean_username = str(
        username
    ).strip().lower()

    document = faces_collection.find_one(
        {
            "username": clean_username
        }
    )

    if not document:

        return None

    face_data = document.get(
        "face_image"
    )

    if face_data is None:

        return None

    return bytes(face_data)


# ============================================================
# DELETE FACE
# ============================================================

def delete_face(username):

    _require_db()

    clean_username = str(
        username
    ).strip().lower()

    faces_collection.delete_one(
        {
            "username": clean_username
        }
    )


# ============================================================
# COMPATIBILITY FUNCTIONS
# ============================================================
#
# These names are used by dashboard/app.py.
# They call the functions above.
# ============================================================

def upsert_user(username, user_record):

    return save_user(
        username,
        user_record
    )


def upsert_users(users):

    return save_users(
        users
    )


def save_face_image(username, face_bytes):

    return save_face(
        username,
        face_bytes
    )


def get_face_image(username):

    return get_face(
        username
    )