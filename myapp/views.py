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

    situation = data.get("situation", "late_to_class")
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
    situation_aliases = {
        "late to class": "late_to_class",
        "late": "late_to_class",
        "missed a deadline": "missed_deadline",
        "missed a assignment deadline": "missed_deadline",
        "missed a call": "skipped_call",
        "skipped a call": "skipped_call",
        "cancelled plans": "cancelled_plans",
    }
    situation = situation_aliases.get(situation.lower(), situation)
    if situation not in {
        "late_to_class",
        "missed_deadline",
        "skipped_call",
        "cancelled_plans",
        "something_else",
    }:
        situation = "something_else"

    excuses_pool = {
        "okish": {
            "late_to_class": [
                "My bus was running behind schedule, but I’m on my way now.",
                "I got held up getting out the door. I’ll be there shortly.",
                "The train was delayed this morning. I’m heading in now.",
            ],
            "missed_deadline": [
                "I hit a snag while wrapping this up. Could I send it over a little later today?",
                "I need a little more time to finish this properly. I’ll have it to you soon.",
                "I’m running behind on the final pass. Would an extension until this afternoon work?",
            ],
            "skipped_call": [
                "I missed your call earlier—sorry about that. Are you free to talk now?",
                "I couldn’t get to my phone in time. Just saw your call and I’m free now.",
                "Sorry I missed you. Send me a time that works and I’ll call back.",
            ],
            "cancelled_plans": [
                "I’m sorry for the late notice, but I can’t make it today. Can we find another time?",
                "Something came up and I need to rain-check. I’d still love to catch up soon.",
                "I need to sit this one out tonight. Could we reschedule for another day?",
            ],
            "something_else": [
                "I got held up unexpectedly. I’m sorting it out and will update you soon.",
                "Today got away from me a little. Thanks for being patient—I’ll check back in shortly.",
                "I ran into an unexpected snag. I’m working on it now and will keep you posted.",
            ],
        },
        "fine": {
            "late_to_class": [
                "The bus I was on had to stop for a mechanical check, so I’m switching routes and heading straight there.",
                "A signal delay backed up the whole route this morning. I’m on the next connection now.",
                "There was an unexpected delay on my way in. I’m moving again and will be there as soon as I can.",
            ],
            "missed_deadline": [
                "I found an issue in the final check and need a little extra time to fix it properly. Could I send it by the end of the day?",
                "The last export didn’t come out right, and I’m correcting it now. Would a short extension be okay?",
                "I’m finishing a final pass so I can send you a clean version. I’ll get it to you later today.",
            ],
            "skipped_call": [
                "I got pulled into something right as you called and couldn’t step away. I’m free now if you still have a minute.",
                "My phone was out of reach while I was dealing with something. I just saw your call—can I ring you back?",
                "I couldn’t get somewhere private to pick up earlier. I can talk now if that still works.",
            ],
            "cancelled_plans": [
                "I overbooked myself and can’t give tonight the attention it deserves. Can we move this to another day?",
                "I need to handle something that came up today, so I have to reschedule. Let me make it up to you soon.",
                "I’m not going to be able to make it tonight after all. I’m sorry for the change—could we pick a new day?",
            ],
            "something_else": [
                "An unexpected issue took longer to sort out than I planned. I’ve got it handled now and will follow up shortly.",
                "I had to take care of something time-sensitive. Thanks for giving me a little room to catch up.",
                "My schedule shifted at the last minute. I’m back on track and will keep you updated.",
            ],
        },
        "master": {
            "late_to_class": [
                "A vehicle issue caused a full stop on my route, so I’ve rerouted and am on my way in. I’ll catch up on anything I miss.",
                "The connection I was relying on got cancelled without notice. I’ve found another way across and should be there soon.",
                "A delay at the station threw off the whole commute. I’m on a different route now and will check in when I arrive.",
            ],
            "missed_deadline": [
                "The final review uncovered a problem that would have affected the result. I’m correcting it now—could I send the finished version this evening?",
                "I had a last-minute issue with the file I was preparing, but I’m rebuilding the final copy now. I can deliver it later today.",
                "I’m not happy with the accuracy of the final version yet. I’m fixing the last issue and will send a complete copy as soon as it’s ready.",
            ],
            "skipped_call": [
                "I got caught in back-to-back commitments and couldn’t step away to call. I’ve got a clear window now if you’re available.",
                "I had to deal with something urgent and missed the time we planned. I’m free now, or I can work around your schedule.",
                "I was away from my phone while I handled a time-sensitive issue. I’m back now—can we find a time to reconnect?",
            ],
            "cancelled_plans": [
                "A time-sensitive responsibility came up and I can’t leave it unfinished tonight. I’m sorry—could I make it up to you this weekend?",
                "I need to stay back and resolve something that changed unexpectedly. I know this is late notice; let me plan a new time.",
                "My evening has shifted because I need to take care of something important. I’m sorry to change plans—can we pick another date?",
            ],
            "something_else": [
                "A time-sensitive issue needed my attention longer than I expected. It’s being handled now, and I’ll send you a proper update shortly.",
                "I had to pivot to resolve something unexpected. I’ve got a plan now and will follow through as soon as I can.",
                "An unplanned commitment changed my timing today. I’m sorting out the next steps and will keep you in the loop.",
            ],
        },
    }
    excuse = random.choice(excuses_pool[level][situation])
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