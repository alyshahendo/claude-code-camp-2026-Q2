import json
import time
import urllib.error
import urllib.request

from .errors import ApiError


class Client:
    """Sends the payload assembled by ``PromptBuilder`` to the API.

    One HTTP POST, one response. No tool loop yet, this just proves the round
    trip works. Failures surface as ``ApiError`` rather than a confusing partial
    or ``None`` result.

    Like the Ruby reference, this uses only the standard library (``urllib``).
    The HTTP call is trivial and should stay visible, not hidden behind a
    third party client.
    """

    RETRYABLE_STATUS_CODES = [408, 409, 429, 500, 502, 503, 504]
    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 0.5

    def __init__(self, builder):
        self._builder = builder

    def call(self, max_output_tokens=1024):
        payload = self._builder.to_api_payload(max_output_tokens=max_output_tokens)
        request = urllib.request.Request(
            self._builder.url(),
            data=json.dumps(payload).encode("utf-8"),
            headers=self._builder.headers(),
            method="POST",
        )
        # SSL is handled automatically: urllib enables it for https URLs and
        # verifies against the system certificate store. Local Ollama uses plain
        # http, so no SSL is needed there.

        attempts = 0
        while True:
            attempts += 1

            try:
                with urllib.request.urlopen(request) as response:
                    status = response.status
                    body = response.read().decode("utf-8")
            except urllib.error.HTTPError as error:
                # An error status still carries a response body. Treat it like a
                # returned response so the status-code retry logic can apply,
                # mirroring how Ruby's net/http hands back a response object.
                status = error.code
                body = error.read().decode("utf-8")
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                # Transient network trouble (connection refused/reset, timeouts,
                # TLS hiccups). Retry with backoff, then give up.
                if attempts > self.MAX_RETRIES:
                    raise ApiError(
                        f"API request failed after {attempts} attempts: "
                        f"{type(error).__name__}: {error}"
                    )
                time.sleep(self._retry_delay(attempts))
                continue

            if self._retryable_response(status) and attempts <= self.MAX_RETRIES:
                time.sleep(self._retry_delay(attempts))
                continue

            break

        if not 200 <= status < 300:
            plural = "" if attempts == 1 else "s"
            raise ApiError(
                f"API request failed after {attempts} attempt{plural} ({status}): {body}"
            )

        return json.loads(body)

    # ---------- private ---------------------------------------------------

    def _retryable_response(self, status):
        return status in self.RETRYABLE_STATUS_CODES

    def _retry_delay(self, attempt):
        return self.BASE_RETRY_DELAY * (2 ** (attempt - 1))
