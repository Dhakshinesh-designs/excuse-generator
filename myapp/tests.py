import json
from unittest.mock import patch
from urllib.error import URLError

from django.test import Client, TestCase, override_settings
from django.urls import include, path

from . import views
from .models import ErrorCode, FAQ, SupportTicket


def failing_view(request):
    raise RuntimeError("test server error")


urlpatterns = [
    path("", include("myproject.urls")),
    path("test-error/", failing_view),
]
handler404 = "myapp.views.custom_404"
handler500 = "myapp.views.custom_500"


class AssessmentPagesTests(TestCase):
    def test_required_pages_render_shared_chat_widget(self):
        for page in ("/", "/faq/", "/errors/", "/about/"):
            with self.subTest(page=page):
                response = self.client.get(page)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Ask assistant")
                self.assertContains(response, "csrfmiddlewaretoken")

    def test_faq_and_error_seed_data_is_present(self):
        self.assertGreaterEqual(FAQ.objects.count(), 10)
        codes = set(ErrorCode.objects.values_list("code", flat=True))
        self.assertTrue(
            {"400", "401", "403", "404", "429", "500", "503", "EGEN-001"}
            <= codes
        )
        self.assertEqual(
            self.client.get("/faq/").context["faqs"].count(),
            FAQ.objects.count(),
        )
        self.assertEqual(
            self.client.get("/errors/").context["error_codes"].count(),
            ErrorCode.objects.count(),
        )

    @override_settings(DEBUG=False)
    def test_unknown_url_uses_custom_404_with_assistant(self):
        response = self.client.get("/this-page-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Ask the assistant", status_code=404)
        self.assertContains(response, "404", status_code=404)

    @override_settings(DEBUG=False, ROOT_URLCONF="myapp.tests")
    def test_server_error_uses_custom_500_with_assistant(self):
        client = Client(raise_request_exception=False)
        response = client.get("/test-error/")
        self.assertEqual(response.status_code, 500)
        self.assertContains(response, "Ask the assistant", status_code=500)

    def test_health_endpoint_reports_sql(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["services"]["sql"], "connected")


class AssistantApiTests(TestCase):
    def post_question(self, question):
        return self.client.post(
            "/api/assistant/",
            data=json.dumps({"question": question}),
            content_type="application/json",
        )

    def test_assistant_explains_http_error_from_sql(self):
        response = self.post_question("What does error 404 mean?")
        self.assertEqual(response.status_code, 200)
        self.assertIn("404", response.json()["answer"])
        self.assertIsNone(response.json()["ticket_reference"])

    def test_assistant_explains_site_specific_error(self):
        response = self.post_question("Explain EGEN-001")
        self.assertEqual(response.status_code, 200)
        self.assertIn("EGEN-001", response.json()["answer"])

    def test_assistant_answers_faq_from_sql(self):
        response = self.post_question("How do I save an excuse to my vault?")
        self.assertEqual(response.status_code, 200)
        self.assertIn("local storage", response.json()["answer"])
        self.assertIsNone(response.json()["ticket_reference"])

    @override_settings(GEMINI_API_KEY="test-key")
    @patch("myapp.services.urlopen")
    def test_assistant_uses_gemini_for_faq_grounded_answer(self, urlopen):
        urlopen.return_value.__enter__.return_value.read.return_value = json.dumps({
            "candidates": [{
                "content": {"parts": [{"text": "The Vault saves it in your browser."}]}
            }]
        }).encode()
        response = self.post_question("Can you tell me something unusual?")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["answer"],
            "The Vault saves it in your browser.",
        )
        self.assertIsNone(response.json()["ticket_reference"])
        request = urlopen.call_args.args[0]
        self.assertIn("gemini-2.5-flash", request.full_url)
        self.assertEqual(request.get_header("X-goog-api-key"), "test-key")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 8)

    def test_unknown_question_creates_sql_support_ticket(self):
        response = self.post_question("Can you tell me about an undocumented feature?")
        self.assertEqual(response.status_code, 200)
        ticket_reference = response.json()["ticket_reference"]
        self.assertTrue(ticket_reference)
        self.assertTrue(
            SupportTicket.objects.filter(reference=ticket_reference, status="open").exists()
        )

    def test_invalid_assistant_payload_is_rejected(self):
        response = self.client.post(
            "/api/assistant/", data="{bad json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    @patch("myapp.views.store_feedback")
    def test_feedback_is_saved_through_mongodb_service(self, store_feedback):
        response = self.client.post(
            "/api/assistant/feedback/",
            data=json.dumps({
                "conversation_id": "test-conversation",
                "helpful": True,
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        store_feedback.assert_called_once_with("test-conversation", True, "")

    @override_settings(MONGODB_URI="")
    def test_feedback_reports_unconfigured_mongodb(self):
        response = self.client.post(
            "/api/assistant/feedback/",
            data=json.dumps({
                "conversation_id": "test-conversation",
                "helpful": False,
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 503)

    @patch("myapp.services.urlopen", side_effect=URLError("offline"))
    def test_inspiration_api_uses_local_fallback(self, urlopen):
        response = self.client.get("/api/inspiration/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source"], "Local fallback")
        urlopen.assert_called_once()

    @patch("myapp.services.urlopen")
    def test_inspiration_api_uses_third_party_response(self, urlopen):
        urlopen.return_value.__enter__.return_value.read.return_value = (
            b'{"setup":"A setup","punchline":"A punchline"}'
        )
        response = self.client.get("/api/inspiration/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["text"], "A setup A punchline")
        self.assertEqual(response.json()["source"], "Official Joke API")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 4)

    def test_excuse_generator_rejects_malformed_json(self):
        response = self.client.post(
            "/api/generate/", data="{bad json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_excuse_generator_uses_existing_api(self):
        response = self.client.post(
            "/api/generate/",
            data=json.dumps({"situation": "a lecture", "level": "okish"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertIn("a lecture", response.json()["excuse"])

    def test_excuse_generator_rejects_invalid_level(self):
        response = self.client.post(
            "/api/generate/",
            data=json.dumps({"situation": "a lecture", "level": []}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
