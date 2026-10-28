import json
import logging
import re
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.conf import settings
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from .models import ErrorCode, FAQ

logger = logging.getLogger(__name__)

STOP_WORDS = {
    "a", "about", "an", "and", "are", "can", "do", "does", "for", "how",
    "i", "in", "is", "it", "me", "my", "of", "on", "or", "the", "this",
    "to", "what", "when", "where", "which", "who", "why", "with", "you",
}

_mongo_client = None
_mongo_profile_index_ready = False


def _tokens(text):
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) > 1 and token not in STOP_WORDS
    }


def _mongo_collection(name):
    global _mongo_client
    uri = settings.MONGODB_URI
    if not uri:
        return None
    if _mongo_client is None:
        _mongo_client = MongoClient(uri, serverSelectionTimeoutMS=1500)
    return _mongo_client[settings.MONGODB_DATABASE][name]


def store_chat_exchange(conversation_id, question, answer, ticket_reference=None):
    try:
        collection = _mongo_collection("chat_logs")
        if collection is None:
            logger.warning("MongoDB is not configured; chat exchange was not persisted.")
            return
        collection.insert_one({
            "conversation_id": conversation_id,
            "question": question,
            "answer": answer,
            "ticket_reference": ticket_reference,
        })
    except PyMongoError as error:
        logger.error("Could not persist chat exchange to MongoDB: %s", error)


def store_feedback(conversation_id, helpful, comment):
    collection = _mongo_collection("feedback")
    if collection is None:
        raise RuntimeError("MongoDB is not configured.")
    collection.insert_one({
        "conversation_id": conversation_id,
        "helpful": helpful,
        "comment": comment,
    })


def _user_profile_collection():
    global _mongo_profile_index_ready
    collection = _mongo_collection("user_profiles")
    if collection is None:
        raise RuntimeError("MongoDB is not configured.")
    if not _mongo_profile_index_ready:
        collection.create_index("django_user_id", unique=True)
        _mongo_profile_index_ready = True
    return collection


def get_user_profile(user_id):
    profile = _user_profile_collection().find_one(
        {"django_user_id": str(user_id)},
        {"_id": False},
    )
    return profile


def create_user_profile(user_id, profile_data):
    document = {
        "django_user_id": str(user_id),
        "display_name": profile_data["display_name"],
        "email": profile_data["email"],
        "bio": profile_data["bio"],
    }
    _user_profile_collection().insert_one(document)
    return document


def update_user_profile(user_id, profile_data):
    result = _user_profile_collection().update_one(
        {"django_user_id": str(user_id)},
        {
            "$set": {
                "display_name": profile_data["display_name"],
                "email": profile_data["email"],
                "bio": profile_data["bio"],
            }
        },
    )
    return result.modified_count > 0 or result.matched_count > 0


def delete_user_profile(user_id):
    result = _user_profile_collection().delete_one(
        {"django_user_id": str(user_id)}
    )
    return result.deleted_count > 0


def mongo_health():
    try:
        collection = _mongo_collection("health_checks")
        if collection is None:
            return "not_configured"
        collection.database.client.admin.command("ping")
        return "connected"
    except PyMongoError as error:
        logger.error("MongoDB health check failed: %s", error)
        return "unavailable"


def answer_from_database(question):
    code_match = re.search(r"\b(?:400|401|403|404|429|500|503|EGEN-001)\b", question.upper())
    if code_match:
        code = code_match.group(0)
        error = ErrorCode.objects.filter(code=code).first()
        if error:
            return (
                f"{error.code} — {error.title}. {error.explanation} "
                f"{error.suggested_action}"
            )

    question_tokens = _tokens(question)
    best_faq = None
    best_score = 0
    best_matches = 0
    for faq in FAQ.objects.all():
        question_terms = _tokens(faq.question)
        keyword_terms = _tokens(faq.keywords)
        answer_terms = _tokens(faq.answer)
        matches = len(question_tokens & (question_terms | keyword_terms))
        score = (
            3 * len(question_tokens & question_terms)
            + 2 * len(question_tokens & keyword_terms)
            + len(question_tokens & answer_terms)
        )
        if score > best_score:
            best_faq, best_score, best_matches = faq, score, matches

    if best_faq and best_matches >= 2:
        return best_faq.answer
    return None


def answer_with_gemini(question):
    if not settings.GEMINI_API_KEY:
        return None

    faq_context = [
        {"question": faq.question, "answer": faq.answer}
        for faq in FAQ.objects.all()
    ]
    error_context = [
        {"code": error.code, "title": error.title,
         "explanation": error.explanation,
         "suggested_action": error.suggested_action}
        for error in ErrorCode.objects.all()
    ]
    payload = {
        "systemInstruction": {
            "parts": [{
                "text": (
                    "Answer only using the supplied FAQ and error-code data. "
                    "Do not invent policies. If the data does not answer the "
                    "question, reply exactly UNKNOWN."
                )
            }]
        },
        "contents": [{
            "parts": [{
                "text": json.dumps({
                    "question": question,
                    "faqs": faq_context,
                    "error_codes": error_context,
                })
            }]
        }],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 300},
    }
    request = Request(
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.5-flash:generateContent",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": settings.GEMINI_API_KEY,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=8) as response:
            result = json.loads(response.read().decode("utf-8"))
        text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
        return None if text.upper() == "UNKNOWN" else text
    except (URLError, TimeoutError, OSError, ValueError, KeyError, IndexError, TypeError) as error:
        logger.warning("Gemini request failed; using the local FAQ matcher: %s", error)
        return None


def get_excuse_inspiration():
    request = Request(
        "https://official-joke-api.appspot.com/random_joke",
        headers={"Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=4) as response:
            result = json.loads(response.read().decode("utf-8"))
        return {
            "text": f"{result['setup']} {result['punchline']}",
            "source": "Official Joke API",
        }
    except (URLError, TimeoutError, OSError, ValueError, KeyError, TypeError) as error:
        logger.warning("Inspiration API unavailable; using local fallback: %s", error)
        return {
            "text": "My calendar and alarm clock agreed on the wrong day.",
            "source": "Local fallback",
        }
