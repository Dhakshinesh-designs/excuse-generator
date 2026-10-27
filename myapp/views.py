import json
import logging
import random
import uuid

from django.conf import settings
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from pymongo.errors import PyMongoError

from .models import ErrorCode, FAQ, SupportTicket
from .services import (
    answer_from_database,
    answer_with_gemini,
    get_excuse_inspiration,
    mongo_health,
    store_chat_exchange,
    store_feedback,
)

logger = logging.getLogger(__name__)


def index(request):
    return render(request, "myapp/index.html")


def faq_page(request):
    return render(request, "myapp/faq.html", {"faqs": FAQ.objects.all()})


def errors_page(request):
    return render(request, "myapp/errors.html", {"error_codes": ErrorCode.objects.all()})


def about_page(request):
    return render(request, "myapp/about.html")


@require_GET
def health_check(request):
    try:
        connection.ensure_connection()
        sql_status = "connected"
    except DatabaseError:
        logger.exception("SQL health check failed.")
        sql_status = "unavailable"

    mongo_status = mongo_health()
    is_healthy = sql_status == "connected" and mongo_status != "unavailable"
    status_code = 200 if is_healthy else 503
    status = "healthy" if is_healthy and mongo_status == "connected" else "degraded"
    return JsonResponse(
        {
            "status": status,
            "services": {
                "sql": sql_status,
                "mongodb": mongo_status,
                "assistant": "configured" if settings_gemini_configured() else "faq-fallback",
            },
        },
        status=status_code,
    )


def settings_gemini_configured():
    return bool(settings.GEMINI_API_KEY)


@require_POST
def generate_excuse(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"status": "error", "message": "Send valid JSON."}, status=400)
    if not isinstance(data, dict):
        return JsonResponse({"status": "error", "message": "Send a JSON object."}, status=400)

    situation = data.get("situation", "late to class")
    level = data.get("level", "fine")
    custom_input = data.get("customInput", "")
    if not isinstance(situation, str) or not isinstance(custom_input, str):
        return JsonResponse(
            {"status": "error", "message": "Situation and custom context must be text."},
            status=400,
        )
    if not isinstance(level, str) or level not in {"okish", "fine", "master"}:
        return JsonResponse(
            {"status": "error", "message": "Choose a valid intensity level."},
            status=400,
        )
    situation = situation[:500]
    custom_input = custom_input[:500]

    excuses_pool = {
        "okish": [
            f"Bro, my alarm decided to ghost me right during {situation}.",
            f"Honestly, I got stuck behind a tractor going 2 mph while dealing with {situation}.",
            f"My dog looked at me so judgmentally that I had to sit down and reevaluate my life regarding {situation}.",
        ],
        "fine": [
            f"Aliens beamed me up right before {situation}, but they dropped me back down in the wrong timezone.",
            f"I was legally obligated by an ancient family curse to investigate a weird noise during {situation}.",
            f"My Wi-Fi router became sentient and locked me out of reality during {situation}.",
        ],
        "master": [
            f"I was secretly recruited by an underground cyberpunk syndicate to prevent a global server meltdown right when {situation} happened.",
            f"A glitch in the matrix temporarily spawned me in a parallel dimension where {situation} doesn't exist yet.",
            f"I had to successfully negotiate a peace treaty between local raccoons holding my keys hostage during {situation}.",
        ],
    }
    excuse = random.choice(excuses_pool.get(level, excuses_pool["fine"]))
    if custom_input:
        excuse = f"Context: '{custom_input}' -> {excuse}"
    return JsonResponse({"status": "success", "excuse": excuse})


@require_POST
def assistant_chat(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Send valid JSON."}, status=400)
    if not isinstance(data, dict):
        return JsonResponse({"error": "Send a JSON object."}, status=400)

    question = data.get("question")
    if not isinstance(question, str) or not question.strip():
        return JsonResponse({"error": "Enter a question first."}, status=400)
    question = question.strip()
    if len(question) > 2000:
        return JsonResponse({"error": "Questions must be 2,000 characters or fewer."}, status=400)

    conversation_id = data.get("conversation_id")
    if not isinstance(conversation_id, str) or len(conversation_id) > 80:
        conversation_id = uuid.uuid4().hex

    answer = answer_from_database(question)
    if answer is None:
        answer = answer_with_gemini(question)

    ticket = None
    if answer is None:
        ticket = SupportTicket.objects.create(question=question)
        answer = (
            "I couldn't find that in the FAQ or error-code guide, so I opened a "
            f"support ticket for follow-up. Your ticket number is {ticket.reference}."
        )

    store_chat_exchange(
        conversation_id, question, answer,
        ticket_reference=ticket.reference if ticket else None,
    )
    return JsonResponse(
        {
            "answer": answer,
            "conversation_id": conversation_id,
            "ticket_reference": ticket.reference if ticket else None,
        }
    )


@require_POST
def assistant_feedback(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Send valid JSON."}, status=400)
    if not isinstance(data, dict):
        return JsonResponse({"error": "Send a JSON object."}, status=400)

    conversation_id = data.get("conversation_id")
    helpful = data.get("helpful")
    comment = data.get("comment", "")
    if (
        not isinstance(conversation_id, str)
        or not conversation_id
        or len(conversation_id) > 80
        or not isinstance(helpful, bool)
        or not isinstance(comment, str)
    ):
        return JsonResponse({"error": "Feedback details are invalid."}, status=400)
    try:
        store_feedback(conversation_id, helpful, comment[:1000])
    except RuntimeError as error:
        logger.warning("%s", error)
        return JsonResponse(
            {"error": "Feedback storage is unavailable; configure MongoDB and try again."},
            status=503,
        )
    except PyMongoError:
        logger.exception("Could not save assistant feedback.")
        return JsonResponse({"error": "Feedback could not be saved."}, status=503)
    return JsonResponse({"status": "saved"})


@require_GET
def excuse_inspiration(request):
    return JsonResponse(get_excuse_inspiration())


def custom_404(request, exception):
    return render(request, "myapp/404.html", status=404)


def custom_500(request):
    return render(request, "myapp/500.html", status=500)