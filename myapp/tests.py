import json
from unittest.mock import patch
from urllib.error import URLError

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import include, path

from . import services
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

    def test_homepage_displays_database_faqs(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Frequently asked")
        self.assertGreaterEqual(response.content.count(b"faq-preview-item"), 10)

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

    @override_settings(MONGODB_URI="")
    def test_health_endpoint_reports_sql(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["services"]["sql"], "connected")


@override_settings(MONGODB_URI="", GEMINI_API_KEY="")
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

    @override_settings(GEMINI_API_KEY="")
    def test_unrelated_question_sharing_one_faq_keyword_creates_ticket(self):
        response = self.post_question(
            "What is the private escalation procedure for international account appeals?"
        )
        self.assertEqual(response.status_code, 200)
        ticket_reference = response.json()["ticket_reference"]
        self.assertTrue(ticket_reference)
        self.assertTrue(
            SupportTicket.objects.filter(reference=ticket_reference, status="open").exists()
        )

    def test_unknown_question_ticket_is_associated_with_signed_in_user(self):
        user = User.objects.create_user(username="ticket-owner", password="test-password")
        self.client.force_login(user)
        response = self.post_question("Can you tell me about an undocumented feature?")
        ticket = SupportTicket.objects.get(reference=response.json()["ticket_reference"])
        self.assertEqual(ticket.user, user)

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
            data=json.dumps({
                "situation": "I do not want to go to class today",
                "level": "okish",
                "customInput": "I woke up late and missed the bus",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertNotIn("context:", response.json()["excuse"].lower())

    def test_situation_and_private_notes_never_appear_in_generated_excuse(self):
        private_reason = "I do not want to go to class today"
        private_detail = "I woke up late and missed the bus"
        for situation in (
            "late_to_class",
            "missed_deadline",
            "skipped_call",
            "cancelled_plans",
            private_reason,
        ):
            with self.subTest(situation=situation):
                response = self.client.post(
                    "/api/generate/",
                    data=json.dumps({
                        "situation": situation,
                        "level": "fine",
                        "customInput": private_detail,
                    }),
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 200)
                excuse = response.json()["excuse"].lower()
                self.assertNotIn(private_reason.lower(), excuse)
                self.assertNotIn(private_detail.lower(), excuse)
                self.assertNotIn("context:", excuse)

    def test_excuse_generator_rejects_invalid_level(self):
        response = self.client.post(
            "/api/generate/",
            data=json.dumps({"situation": "a lecture", "level": []}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)


class AccountTests(TestCase):
    def test_registration_creates_hashed_password_and_signs_user_in(self):
        response = self.client.post(
            "/accounts/register/",
            {
                "username": "profile-user",
                "password1": "Strong-test-password-2026!",
                "password2": "Strong-test-password-2026!",
            },
        )
        self.assertRedirects(response, "/accounts/profile/", fetch_redirect_response=False)
        user = User.objects.get(username="profile-user")
        self.assertNotEqual(user.password, "Strong-test-password-2026!")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_profile_requires_login(self):
        response = self.client.get("/accounts/profile/")
        self.assertRedirects(
            response,
            "/accounts/login/?next=/accounts/profile/",
            fetch_redirect_response=False,
        )

    @patch("myapp.views.get_user_profile", return_value=None)
    @patch("myapp.views.create_user_profile")
    def test_profile_creates_mongodb_document(self, create_profile, get_profile):
        user = User.objects.create_user(username="create-profile", password="test-password")
        self.client.force_login(user)
        response = self.client.post(
            "/accounts/profile/",
            {
                "action": "save",
                "display_name": "A User",
                "email": "a-user@example.test",
                "bio": "Hello",
            },
        )
        self.assertRedirects(response, "/accounts/profile/", fetch_redirect_response=False)
        get_profile.assert_called_once_with(user.pk)
        create_profile.assert_called_once_with(
            user.pk,
            {"display_name": "A User", "email": "a-user@example.test", "bio": "Hello"},
        )

    @patch("myapp.views.get_user_profile")
    @patch("myapp.views.update_user_profile", return_value=True)
    def test_profile_updates_only_the_signed_in_users_document(
        self, update_profile, get_profile
    ):
        user = User.objects.create_user(username="update-profile", password="test-password")
        get_profile.return_value = {
            "django_user_id": str(user.pk),
            "display_name": "Before",
            "email": "",
            "bio": "",
        }
        self.client.force_login(user)
        response = self.client.post(
            "/accounts/profile/",
            {
                "action": "save",
                "display_name": "After",
                "email": "",
                "bio": "Updated",
            },
        )
        self.assertRedirects(response, "/accounts/profile/", fetch_redirect_response=False)
        update_profile.assert_called_once_with(
            user.pk,
            {"display_name": "After", "email": "", "bio": "Updated"},
        )

    @patch("myapp.views.delete_user_profile", return_value=True)
    def test_profile_deletes_its_mongodb_document(self, delete_profile):
        user = User.objects.create_user(username="delete-profile", password="test-password")
        self.client.force_login(user)
        response = self.client.post("/accounts/profile/", {"action": "delete"})
        self.assertRedirects(response, "/accounts/profile/", fetch_redirect_response=False)
        delete_profile.assert_called_once_with(user.pk)

    @patch("myapp.views.get_user_profile", side_effect=RuntimeError("unavailable"))
    def test_profile_shows_mongodb_storage_error(self, get_profile):
        user = User.objects.create_user(username="offline-profile", password="test-password")
        self.client.force_login(user)
        response = self.client.get("/accounts/profile/")
        self.assertEqual(response.status_code, 503)
        self.assertContains(response, "MongoDB profile storage is unavailable", status_code=503)
        get_profile.assert_called_once_with(user.pk)


class MongoProfileServiceTests(TestCase):
    @patch("myapp.services._user_profile_collection")
    def test_profile_read_looks_up_only_its_owner(self, get_collection):
        profile = {
            "django_user_id": "17",
            "display_name": "A User",
            "email": "",
            "bio": "",
        }
        get_collection.return_value.find_one.return_value = profile
        self.assertEqual(services.get_user_profile(17), profile)
        get_collection.return_value.find_one.assert_called_once_with(
            {"django_user_id": "17"},
            {"_id": False},
        )

    @patch("myapp.services._user_profile_collection")
    def test_profile_create_writes_owner_and_profile_fields(self, get_collection):
        profile_data = {"display_name": "A User", "email": "a@example.test", "bio": "Hi"}
        self.assertEqual(services.create_user_profile(17, profile_data), {
            "django_user_id": "17",
            **profile_data,
        })
        get_collection.return_value.insert_one.assert_called_once_with({
            "django_user_id": "17",
            **profile_data,
        })

    @patch("myapp.services._user_profile_collection")
    def test_profile_update_filters_by_owner(self, get_collection):
        collection = get_collection.return_value
        collection.update_one.return_value.matched_count = 1
        collection.update_one.return_value.modified_count = 1
        profile_data = {"display_name": "New", "email": "", "bio": "Updated"}
        self.assertTrue(services.update_user_profile(17, profile_data))
        collection.update_one.assert_called_once_with(
            {"django_user_id": "17"},
            {"$set": profile_data},
        )

    @patch("myapp.services._user_profile_collection")
    def test_profile_delete_filters_by_owner(self, get_collection):
        collection = get_collection.return_value
        collection.delete_one.return_value.deleted_count = 1
        self.assertTrue(services.delete_user_profile(17))
        collection.delete_one.assert_called_once_with({"django_user_id": "17"})
