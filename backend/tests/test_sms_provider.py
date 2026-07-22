import os
import unittest
from unittest.mock import AsyncMock, patch

try:
    import sms_provider
except ModuleNotFoundError:
    sms_provider = None


@unittest.skipIf(sms_provider is None, "backend runtime dependencies are not installed")
class SmsProviderTests(unittest.IsolatedAsyncioTestCase):
    def test_provider_defaults_to_legacy_during_transition(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(sms_provider.alert_provider_name(), "africastalking")

    def test_twilio_requires_credentials_and_sender(self):
        with patch.dict(os.environ, {"TWILIO_ACCOUNT_SID": "AC1", "TWILIO_AUTH_TOKEN": "secret"}, clear=True):
            self.assertFalse(sms_provider.twilio_configured())
        with patch.dict(os.environ, {
            "TWILIO_ACCOUNT_SID": "AC1", "TWILIO_AUTH_TOKEN": "secret",
            "TWILIO_MESSAGING_SERVICE_SID": "MG1",
        }, clear=True):
            self.assertTrue(sms_provider.twilio_configured())

    async def test_twilio_switch_does_not_call_legacy_provider(self):
        with patch.dict(os.environ, {"ALERT_SMS_PROVIDER": "twilio"}), \
             patch.object(sms_provider, "_send_twilio_sms", AsyncMock(return_value="SM1")) as twilio, \
             patch.object(sms_provider, "send_africas_talking_sms", AsyncMock()) as legacy:
            provider_id, provider = await sms_provider.send_alert_sms("2348012345678", "Watch conditions")
        self.assertEqual((provider_id, provider), ("SM1", "twilio"))
        twilio.assert_awaited_once()
        legacy.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
