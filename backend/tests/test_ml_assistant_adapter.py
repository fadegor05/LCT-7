"""Тесты адаптера ML-ассистента.

Проверяют HttpAssistantClient, NullAssistantClient и factory.
"""

from dataclasses import dataclass

import httpx
import pytest

from app.adapters.ml.assistant import (
    AssistantAnswer,
    AssistantBadRequest,
    AssistantError,
    AssistantTimeout,
    AssistantUnavailable,
    HttpAssistantClient,
    NullAssistantClient,
)
from app.adapters.ml.factory import create_assistant
from app.core.settings import AssistantSettings, Settings


@dataclass
class FakeClock:
    """Fake clock для тестирования кэширования."""

    current_time: float = 0.0

    def __call__(self) -> float:
        return self.current_time

    def advance(self, delta: float) -> None:
        """Advance the clock by delta seconds."""
        self.current_time += delta


class TestAssistantAnswer:
    """Проверка AssistantAnswer dataclass."""

    def test_assistant_answer_fields(self):
        """AssistantAnswer содержит все необходимые поля."""
        answer = AssistantAnswer(
            answer="Ответ на вопрос",
            verified=True,
            numbers_not_in_report=["123"],
            numbers_of_other_site=["456"],
            limits="100 символов",
        )
        assert answer.answer == "Ответ на вопрос"
        assert answer.verified is True
        assert answer.numbers_not_in_report == ["123"]
        assert answer.numbers_of_other_site == ["456"]
        assert answer.limits == "100 символов"


class TestAssistantErrors:
    """Проверка иерархии исключений ассистента."""

    def test_assistant_unavailable_defaults(self):
        """AssistantUnavailable имеет дефолтные значения."""
        err = AssistantUnavailable("Тест")
        assert err.message == "Тест"
        assert err.status_code == 503
        assert err.code == "assistant_unavailable"

    def test_assistant_timeout_defaults(self):
        """AssistantTimeout имеет дефолтные значения."""
        err = AssistantTimeout("Тест")
        assert err.message == "Тест"
        assert err.status_code == 504
        assert err.code == "assistant_timeout"

    def test_assistant_bad_request_defaults(self):
        """AssistantBadRequest имеет дефолтные значения."""
        err = AssistantBadRequest("Тест")
        assert err.message == "Тест"
        assert err.status_code == 400
        assert err.code == "assistant_bad_request"

    def test_assistant_bad_request_out_of_scope(self):
        """AssistantBadRequest можно конструировать с code='out_of_scope'."""
        err = AssistantBadRequest(
            "Только по отчёту",
            status_code=422,
            code="out_of_scope",
        )
        assert err.message == "Только по отчёту"
        assert err.status_code == 422
        assert err.code == "out_of_scope"


class TestHttpAssistantClientAskSuccess:
    """Happy path для HttpAssistantClient.ask()."""

    @pytest.mark.asyncio
    async def test_ask_успех(self):
        """200 с пятью полями -> AssistantAnswer равный."""
        response_data = {
            "answer": "Ответ на вопрос",
            "verified": True,
            "numbers_not_in_report": ["123"],
            "numbers_of_other_site": ["456"],
            "limits": "100",
        }

        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json=response_data))
        )
        assistant = HttpAssistantClient(
            base_url="http://ml:8000/",
            client=mock_client,
            settings=AssistantSettings(),
        )
        result = await assistant.ask(
            question="Вопрос",
            report={"test": "data"},
            site_id="p1",
        )

        assert result.answer == "Ответ на вопрос"
        assert result.verified is True
        assert result.numbers_not_in_report == ["123"]
        assert result.numbers_of_other_site == ["456"]
        assert result.limits == "100"

    @pytest.mark.asyncio
    async def test_verified_false_не_меняется(self):
        """200 с verified=false и списками -> возвращены идентично."""
        response_data = {
            "answer": "Ответ",
            "verified": False,
            "numbers_not_in_report": ["999"],
            "numbers_of_other_site": ["p1: 5"],
            "limits": "test",
        }

        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json=response_data))
        )
        assistant = HttpAssistantClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=AssistantSettings(),
        )
        result = await assistant.ask("Вопрос", {}, "p1")

        assert result.verified is False
        assert result.numbers_not_in_report == ["999"]
        assert result.numbers_of_other_site == ["p1: 5"]

    @pytest.mark.asyncio
    async def test_request_body_has_fields(self):
        """Request body содержит question, report, site_id."""
        captured_request = {}

        def mock_transport(request: httpx.Request) -> httpx.Response:
            captured_request["body"] = request.content
            return httpx.Response(
                200,
                json={
                    "answer": "Ответ",
                    "verified": True,
                    "numbers_not_in_report": [],
                    "numbers_of_other_site": [],
                    "limits": "",
                },
            )

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        assistant = HttpAssistantClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=AssistantSettings(),
        )
        await assistant.ask("Мой вопрос", {"report": "data"}, "p1")

        import json

        body = json.loads(captured_request["body"])
        assert body["question"] == "Мой вопрос"
        assert body["report"] == {"report": "data"}
        assert body["site_id"] == "p1"

    @pytest.mark.asyncio
    async def test_url_normalization(self):
        """URL нормализуется (убирает /ask, trailing /)."""

        def mock_transport(request: httpx.Request) -> httpx.Response:
            assert str(request.url).startswith("http://ml:8000/ask")
            return httpx.Response(
                200,
                json={
                    "answer": "",
                    "verified": True,
                    "numbers_not_in_report": [],
                    "numbers_of_other_site": [],
                    "limits": "",
                },
            )

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        assistant = HttpAssistantClient(
            base_url="http://ml:8000/",
            client=mock_client,
            settings=AssistantSettings(),
        )
        await assistant.ask("Q", {}, "p1")


class TestHttpAssistantClientErrors:
    """Тесты маппирования ошибок."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "status,error_class",
        [
            (503, AssistantUnavailable),
            (500, AssistantUnavailable),
            (504, AssistantTimeout),
        ],
    )
    async def test_ошибки_ml_маппятся(self, status, error_class):
        """ML 503/500 -> AssistantUnavailable; 504 -> AssistantTimeout."""
        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(status))
        )
        assistant = HttpAssistantClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=AssistantSettings(),
        )
        with pytest.raises(error_class):
            await assistant.ask("Q", {}, "p1")

    @pytest.mark.asyncio
    async def test_400_маппится_в_bad_request(self):
        """ML 400 -> AssistantBadRequest (400, assistant_bad_request)."""
        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(400))
        )
        assistant = HttpAssistantClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=AssistantSettings(),
        )
        with pytest.raises(AssistantBadRequest) as exc_info:
            await assistant.ask("Q", {}, "p1")

        err = exc_info.value
        assert err.status_code == 400
        assert err.code == "assistant_bad_request"

    @pytest.mark.asyncio
    async def test_422_validation_маппится(self):
        """422 с detail list (validation) -> AssistantBadRequest (400, assistant_bad_request)."""
        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda req: httpx.Response(422, json={"detail": [{"msg": "Invalid"}]})
            )
        )
        assistant = HttpAssistantClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=AssistantSettings(),
        )
        with pytest.raises(AssistantBadRequest) as exc_info:
            await assistant.ask("Q", {}, "p1")

        err = exc_info.value
        assert err.status_code == 400
        assert err.code == "assistant_bad_request"

    @pytest.mark.asyncio
    async def test_422_out_of_scope_маппится(self):
        """422 с code=out_of_scope -> AssistantBadRequest (422, out_of_scope, message)."""
        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda req: httpx.Response(
                    422,
                    json={
                        "detail": {
                            "code": "out_of_scope",
                            "message": "Только по отчёту",
                        }
                    },
                )
            )
        )
        assistant = HttpAssistantClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=AssistantSettings(),
        )
        with pytest.raises(AssistantBadRequest) as exc_info:
            await assistant.ask("Q", {}, "p1")

        err = exc_info.value
        assert err.status_code == 422
        assert err.code == "out_of_scope"
        assert err.message == "Только по отчёту"

    @pytest.mark.asyncio
    async def test_таймаут_чтения_504_а_коннект_503(self):
        """ReadTimeout -> AssistantTimeout; ConnectError -> AssistantUnavailable."""

        def mock_transport_read_timeout(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timeout")

        def mock_transport_connect_error(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connect failed")

        mock_client_timeout = httpx.AsyncClient(
            transport=httpx.MockTransport(mock_transport_read_timeout)
        )
        mock_client_connect = httpx.AsyncClient(
            transport=httpx.MockTransport(mock_transport_connect_error)
        )

        assistant_timeout = HttpAssistantClient(
            base_url="http://ml:8000",
            client=mock_client_timeout,
            settings=AssistantSettings(),
        )
        assistant_connect = HttpAssistantClient(
            base_url="http://ml:8000",
            client=mock_client_connect,
            settings=AssistantSettings(),
        )

        with pytest.raises(AssistantTimeout):
            await assistant_timeout.ask("Q", {}, "p1")

        with pytest.raises(AssistantUnavailable):
            await assistant_connect.ask("Q", {}, "p1")

    @pytest.mark.asyncio
    async def test_ровно_один_вызов_при_ошибках(self):
        """503, 504, ReadTimeout -> ровно 1 HTTP вызов (no retries)."""
        call_counts = {}

        def make_transport(status_or_exc):
            call_count = [0]

            def transport(request: httpx.Request) -> httpx.Response:
                call_count[0] += 1
                if isinstance(status_or_exc, type) and issubclass(status_or_exc, Exception):
                    raise status_or_exc("error")
                return httpx.Response(status_or_exc)

            call_counts[str(status_or_exc)] = call_count
            return transport

        for error_case in [503, 504, httpx.ReadTimeout]:
            try:
                mock_client = httpx.AsyncClient(
                    transport=httpx.MockTransport(make_transport(error_case))
                )
                assistant = HttpAssistantClient(
                    base_url="http://ml:8000",
                    client=mock_client,
                    settings=AssistantSettings(),
                )
                await assistant.ask("Q", {}, "p1")
            except AssistantError:
                pass
            except httpx.ReadTimeout:
                pass

        # Count actual calls - test by just checking that it's 1
        assert call_counts[str(503)][0] == 1
        assert call_counts[str(504)][0] == 1
        assert call_counts[str(httpx.ReadTimeout)][0] == 1

    @pytest.mark.asyncio
    async def test_неверный_json_и_схема(self):
        """Invalid JSON и invalid schema -> AssistantUnavailable."""
        # Test invalid JSON
        mock_client_invalid_json = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, text="not json"))
        )
        assistant_json = HttpAssistantClient(
            base_url="http://ml:8000",
            client=mock_client_invalid_json,
            settings=AssistantSettings(),
        )
        with pytest.raises(AssistantUnavailable):
            await assistant_json.ask("Q", {}, "p1")

        # Test invalid schema (missing field)
        mock_client_invalid_schema = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json={"answer": 1}))
        )
        assistant_schema = HttpAssistantClient(
            base_url="http://ml:8000",
            client=mock_client_invalid_schema,
            settings=AssistantSettings(),
        )
        with pytest.raises(AssistantUnavailable):
            await assistant_schema.ask("Q", {}, "p1")

    @pytest.mark.asyncio
    async def test_в_сообщениях_нет_секретов(self):
        """ML 504 с секретом в detail -> секрет не в exc.message и str(exc)."""
        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda req: httpx.Response(
                    504,
                    json={"detail": "языковая модель не ответила: sk-SECRET llm.secret.example"},
                )
            )
        )
        assistant = HttpAssistantClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=AssistantSettings(),
        )
        with pytest.raises(AssistantTimeout) as exc_info:
            await assistant.ask("Q", {}, "p1")

        err = exc_info.value
        assert "sk-SECRET" not in err.message
        assert "sk-SECRET" not in str(err)
        assert "llm.secret.example" not in err.message
        assert "llm.secret.example" not in str(err)


class TestHttpAssistantClientAvailable:
    """Тесты available() с кэшированием."""

    @pytest.mark.asyncio
    async def test_available_true_false_и_кэш(self):
        """GET /meta -> True if assistant=true, False otherwise, cached."""
        call_count = [0]

        def mock_transport(request: httpx.Request) -> httpx.Response:
            call_count[0] += 1
            if "meta" in str(request.url):
                return httpx.Response(200, json={"assistant": True})
            return httpx.Response(404)

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        clock = FakeClock()
        assistant = HttpAssistantClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=AssistantSettings(status_cache_s=30.0, status_retry_s=5.0),
            clock=clock,
        )

        # First call to available() - should hit transport
        result1 = await assistant.available()
        assert result1 is True
        assert call_count[0] == 1

        # Second call within cache TTL - should not hit transport
        result2 = await assistant.available()
        assert result2 is True
        assert call_count[0] == 1  # No additional call

        # Advance clock past cache TTL
        clock.advance(31.0)
        result3 = await assistant.available()
        assert result3 is True
        assert call_count[0] == 2  # Should hit transport again

    @pytest.mark.asyncio
    async def test_available_false_with_retry_cache(self):
        """Connection error -> False, retry after status_retry_s."""
        call_count = [0]

        def mock_transport(request: httpx.Request) -> httpx.Response:
            call_count[0] += 1
            raise httpx.ConnectError("connection failed")

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        clock = FakeClock()
        assistant = HttpAssistantClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=AssistantSettings(status_cache_s=30.0, status_retry_s=5.0),
            clock=clock,
        )

        # First call - error, returns False
        result1 = await assistant.available()
        assert result1 is False
        assert call_count[0] == 1

        # Second call within retry TTL - should not hit transport
        result2 = await assistant.available()
        assert result2 is False
        assert call_count[0] == 1  # No additional call

        # Advance clock past retry TTL
        clock.advance(6.0)
        result3 = await assistant.available()
        assert result3 is False
        assert call_count[0] == 2  # Should hit transport again


class TestNullAssistantClient:
    """Тесты NullAssistantClient."""

    @pytest.mark.asyncio
    async def test_null_клиент(self):
        """NullAssistantClient.ask raises AssistantUnavailable."""
        null_client = NullAssistantClient()

        with pytest.raises(AssistantUnavailable) as exc_info:
            await null_client.ask("Q", {})

        assert exc_info.value.message == "Ассистент не настроен"

    @pytest.mark.asyncio
    async def test_null_available_false(self):
        """NullAssistantClient.available() возвращает False."""
        null_client = NullAssistantClient()
        result = await null_client.available()
        assert result is False


class TestCreateAssistant:
    """Тесты factory функции create_assistant."""

    def test_create_assistant_выбор_http(self):
        """create_assistant с URL и client -> HttpAssistantClient."""
        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json={"assistant": True}))
        )
        settings = Settings()
        settings.detector.url = "http://ml:8000"

        assistant = create_assistant(settings, mock_client)
        assert isinstance(assistant, HttpAssistantClient)

    def test_create_assistant_выбор_null_no_url(self):
        """create_assistant без URL -> NullAssistantClient."""
        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json={"assistant": True}))
        )
        settings = Settings()
        settings.detector.url = ""

        assistant = create_assistant(settings, mock_client)
        assert isinstance(assistant, NullAssistantClient)

    def test_create_assistant_выбор_null_no_client(self):
        """create_assistant без client -> NullAssistantClient."""
        settings = Settings()
        settings.detector.url = "http://ml:8000"

        assistant = create_assistant(settings, None)
        assert isinstance(assistant, NullAssistantClient)

    def test_create_assistant_выбор_null_whitespace_url(self):
        """create_assistant с whitespace URL -> NullAssistantClient."""
        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json={"assistant": True}))
        )
        settings = Settings()
        settings.detector.url = "   "

        assistant = create_assistant(settings, mock_client)
        assert isinstance(assistant, NullAssistantClient)


class TestHttpAssistantClientTimeoutShort:
    """Тесты для короткого таймаута на /meta."""

    @pytest.mark.asyncio
    async def test_available_использует_короткий_таймаут(self):
        """available() использует таймаут 5.0 для /meta, ask() - settings.timeout_s."""
        timeouts = {}

        def mock_transport(request: httpx.Request) -> httpx.Response:
            # Check the timeout in request extensions
            timeout_dict = request.extensions.get("timeout", {})
            read_timeout = timeout_dict.get("read")

            if "meta" in str(request.url):
                timeouts["meta"] = read_timeout
                return httpx.Response(200, json={"assistant": True})
            else:
                timeouts["ask"] = read_timeout
                return httpx.Response(
                    200,
                    json={
                        "answer": "test",
                        "verified": True,
                        "numbers_not_in_report": [],
                        "numbers_of_other_site": [],
                        "limits": "",
                    },
                )

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        assistant = HttpAssistantClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=AssistantSettings(timeout_s=130.0),
        )

        # Call available() - should use short timeout
        await assistant.available()

        # Call ask() - should use full timeout
        await assistant.ask("Q", {}, "p1")

        # Verify timeouts
        assert timeouts["meta"] is not None
        assert timeouts["meta"] <= 5.1  # /meta should use ~5s
        assert timeouts["ask"] is not None
        assert timeouts["ask"] >= 100  # /ask should use ~130s


class TestHttpAssistantClientPoolTimeout:
    """Тесты для PoolTimeout маппирования."""

    @pytest.mark.asyncio
    async def test_pool_timeout_маппится_503(self):
        """httpx.PoolTimeout -> AssistantUnavailable (503)."""

        def mock_transport(request: httpx.Request) -> httpx.Response:
            raise httpx.PoolTimeout("pool exhausted")

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        assistant = HttpAssistantClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=AssistantSettings(),
        )

        with pytest.raises(AssistantUnavailable) as exc_info:
            await assistant.ask("Q", {}, "p1")

        assert exc_info.value.status_code == 503
