import time
import uuid

import jwt
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from .models import ConsumedLaunchToken, ExternalIdentityLink


SECRET = "test-ugi-sso-secret"


@override_settings(UGI_CRM_SSO_SIGNING_SECRET=SECRET, LOGIN_REDIRECT_URL="/teacher/recordings/")
class UgiSsoConsumeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="teacher", password="unused")
        self.subject = "11111111-1111-4111-8111-111111111111"
        ExternalIdentityLink.objects.create(
            provider="ugi-crm",
            subject=self.subject,
            user=self.user,
            email_at_link="teacher@ugi.edu.pk",
            active=True,
        )

    def token(self, **overrides):
        now = int(time.time())
        claims = {
            "sub": self.subject,
            "email": "teacher@ugi.edu.pk",
            "jti": str(uuid.uuid4()),
            "iat": now,
            "exp": now + 60,
            "iss": "ugi-crm",
            "aud": "ai-lecture-system",
        }
        claims.update(overrides)
        return jwt.encode(claims, SECRET, algorithm="HS256")

    def test_get_is_rejected(self):
        self.assertEqual(self.client.get("/auth/ugi/consume").status_code, 405)

    def test_valid_link_creates_session_and_consumes_jti_once(self):
        token = self.token()
        response = self.client.post("/auth/ugi/consume", {"token": token})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/teacher/recordings/")
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)
        self.assertEqual(ConsumedLaunchToken.objects.count(), 1)
        self.assertEqual(self.client.post("/auth/ugi/consume", {"token": token}).status_code, 403)

    def test_unlinked_and_inactive_identity_are_rejected(self):
        self.assertEqual(self.client.post("/auth/ugi/consume", {"token": self.token(sub="other")}).status_code, 403)
        ExternalIdentityLink.objects.filter(subject=self.subject).update(active=False)
        self.assertEqual(self.client.post("/auth/ugi/consume", {"token": self.token()}).status_code, 403)

    def test_expired_wrong_issuer_wrong_audience_and_wrong_signature_are_rejected(self):
        now = int(time.time())
        cases = [
            self.token(iat=now - 120, exp=now - 60),
            self.token(iss="other"),
            self.token(aud="other"),
            jwt.encode({"sub": self.subject, "jti": str(uuid.uuid4()), "iat": now, "exp": now + 60, "iss": "ugi-crm", "aud": "ai-lecture-system"}, "wrong", algorithm="HS256"),
        ]
        for token in cases:
            with self.subTest(token=token[:16]):
                self.assertEqual(self.client.post("/auth/ugi/consume", {"token": token}).status_code, 403)

    def test_malformed_token_and_unsafe_next_are_handled_safely(self):
        self.assertEqual(self.client.post("/auth/ugi/consume", {"token": "not-a-jwt"}).status_code, 403)
        response = self.client.post("/auth/ugi/consume", {"token": self.token(), "next": "https://evil.example/"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/teacher/recordings/")
