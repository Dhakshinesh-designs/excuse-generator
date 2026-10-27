from django.db import migrations


FAQS = [
    (
        "How do I generate an excuse?",
        "Open the Generator page, enter your situation, choose an intensity level, and press Generate Excuse.",
        "generate generator create make new excuse",
    ),
    (
        "What do the intensity levels mean?",
        "Okish gives a casual response, Fine gives a more dramatic one, and Master Level produces the most elaborate response.",
        "levels intensity okish fine master vibe",
    ),
    (
        "How do I save an excuse?",
        "After generating an excuse, choose Save Vault. Saved excuses are kept in this browser's local storage.",
        "save vault bookmark store browser local",
    ),
    (
        "How do I copy or share an excuse?",
        "Use Copy on the result card, or open Flex Text to preview the excuse as a message before copying it.",
        "copy share clipboard flex text message",
    ),
    (
        "Do I need an account?",
        "No account is required to use the generator, browse FAQs, or ask the assistant.",
        "account sign up login register",
    ),
    (
        "Does the generator need an AI key?",
        "No. The local generator and FAQ assistant have fallbacks. A Gemini API key enables AI-generated answers grounded in this site's FAQ and error-code data.",
        "AI Gemini key api fallback assistant",
    ),
    (
        "What happens when the assistant cannot answer?",
        "The assistant opens a support ticket in the SQL database and returns a ticket reference you can keep.",
        "assistant cannot answer unknown support ticket help",
    ),
    (
        "Where are chat logs and feedback stored?",
        "Chat logs and assistant feedback are stored in MongoDB when MONGODB_URI is configured by the site operator.",
        "chat logs feedback mongodb storage privacy",
    ),
    (
        "Are my generated excuses stored on the server?",
        "Generated excuses are not saved to the server automatically. The Vault saves them locally in your browser.",
        "data stored privacy generated excuses server",
    ),
    (
        "How do I report a problem?",
        "Open the assistant and describe the problem. If the FAQ cannot answer, the assistant creates a support ticket and shows its reference.",
        "report issue problem support contact ticket",
    ),
    (
        "What does EGEN-001 mean?",
        "EGEN-001 is the site's custom excuse-generation error code. It means the generator could not complete the request; retry, and contact support if it continues.",
        "EGEN-001 generator custom site-specific error",
    ),
    (
        "Where can I check whether the service is working?",
        "The /health/ page checks the SQL database and reports MongoDB and assistant configuration status.",
        "health status service database",
    ),
]

ERRORS = [
    (
        "400",
        "Bad Request",
        "The request was malformed or contained invalid input.",
        "Check the form fields and send valid JSON when using an API.",
    ),
    (
        "401",
        "Unauthorized",
        "The requested resource requires valid authentication.",
        "Sign in with an authorized account or check the credentials for your request.",
    ),
    (
        "403",
        "Forbidden",
        "The server understood the request but will not allow access.",
        "Check your permissions and retry after signing in if appropriate.",
    ),
    (
        "404",
        "Page Not Found",
        "The requested page does not exist at that address.",
        "Check the URL or return to the generator and use the site navigation.",
    ),
    (
        "429",
        "Too Many Requests",
        "Too many requests were sent in a short period.",
        "Wait briefly before trying again.",
    ),
    (
        "500",
        "Internal Server Error",
        "The server encountered an unexpected problem while processing the request.",
        "Retry in a moment. If the problem persists, ask the assistant to open a support ticket.",
    ),
    (
        "503",
        "Service Unavailable",
        "The service or one of its dependencies is temporarily unavailable.",
        "Try again shortly and check the /health/ page for dependency status.",
    ),
    (
        "EGEN-001",
        "Excuse Generation Failed",
        "The site's excuse generator could not complete the request.",
        "Check your situation text and retry. If it continues, ask the assistant to create a support ticket.",
    ),
]


def seed_content(apps, schema_editor):
    FAQ = apps.get_model("myapp", "FAQ")
    ErrorCode = apps.get_model("myapp", "ErrorCode")
    for order, (question, answer, keywords) in enumerate(FAQS, start=1):
        FAQ.objects.update_or_create(
            question=question,
            defaults={"answer": answer, "keywords": keywords, "order": order},
        )
    for order, (code, title, explanation, suggested_action) in enumerate(ERRORS, start=1):
        ErrorCode.objects.update_or_create(
            code=code,
            defaults={
                "title": title,
                "explanation": explanation,
                "suggested_action": suggested_action,
                "order": order,
            },
        )


def unseed_content(apps, schema_editor):
    FAQ = apps.get_model("myapp", "FAQ")
    ErrorCode = apps.get_model("myapp", "ErrorCode")
    FAQ.objects.filter(question__in=[item[0] for item in FAQS]).delete()
    ErrorCode.objects.filter(code__in=[item[0] for item in ERRORS]).delete()


class Migration(migrations.Migration):
    dependencies = [("myapp", "0001_initial")]

    operations = [migrations.RunPython(seed_content, unseed_content)]
