import unittest
from unittest.mock import Mock, patch

import requests

import model_client


class GenerateFixTests(unittest.TestCase):
    def test_sends_configured_auth_and_parses_completion(self):
        response = Mock()
        response.json.return_value = {
            "model": "local-model",
            "choices": [{"message": {"content": '{"fixed_sql":"SELECT 1"}'}}],
        }
        with patch.object(model_client, "API_KEY", "test-key"), patch.object(
            model_client.requests, "post", return_value=response
        ) as post:
            result = model_client.generate_fix("SELECT 1", "items(id)")

        self.assertEqual(result["raw_response"], '{"fixed_sql":"SELECT 1"}')
        self.assertEqual(result["model"], "local-model")
        self.assertEqual(
            post.call_args.kwargs["headers"]["Authorization"], "Bearer test-key"
        )
        response.raise_for_status.assert_called_once()

    def test_invalid_completion_shape_raises_clear_error(self):
        response = Mock()
        response.json.return_value = {"choices": []}
        with patch.object(model_client.requests, "post", return_value=response):
            with self.assertRaisesRegex(model_client.ModelResponseError, "invalid"):
                model_client.generate_fix("SELECT 1", "items(id)")

    def test_empty_completion_is_rejected(self):
        response = Mock()
        response.json.return_value = {
            "choices": [{"message": {"content": " "}}],
        }
        with patch.object(model_client.requests, "post", return_value=response):
            with self.assertRaisesRegex(model_client.ModelResponseError, "empty"):
                model_client.generate_fix("SELECT 1", "items(id)")

    def test_empty_query_is_rejected_without_network_request(self):
        with patch.object(model_client.requests, "post") as post:
            with self.assertRaisesRegex(ValueError, "SQL query"):
                model_client.generate_fix(" ", "items(id)")

        post.assert_not_called()

    def test_http_errors_are_propagated(self):
        with patch.object(
            model_client.requests,
            "post",
            side_effect=requests.ConnectionError("offline"),
        ):
            with self.assertRaises(requests.ConnectionError):
                model_client.generate_fix("SELECT 1", "items(id)")


if __name__ == "__main__":
    unittest.main()
