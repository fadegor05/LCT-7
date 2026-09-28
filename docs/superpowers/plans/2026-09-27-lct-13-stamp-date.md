# LCT-13: Дата со штампа через ML (`POST /stamp` + `HttpStampReader`)

> **For agentic workers:** implement task-by-task. Run tests after each task. Do not skip the "Ruling" section — it fixes design decisions the ticket left open.

**Linear:** LCT-13 — https://linear.app/kaiangel/issue/LCT-13/data-so-shtampa-cherez-ml-post-stamp-i-httpstampreader-v-bekende

**Base branch:** `main` (current tip after LCT-16/LCT-14/LCT-15). New branch: `claude/lct-13-stamp-date`.

## Ruling (decisions the ticket left implicit)

1. **`DateResolver.resolve()` becomes `async`.** Today it's fully sync and called via `await asyncio.to_thread(self._resolver.resolve, content)` in `photo/service.py:211`. `HttpStampReader` must make an async HTTP call, and you cannot `await` inside a plain thread (no event loop there). So: `resolve()` becomes `async def`, its own image-decode step wraps the sync PIL work in `asyncio.to_thread` internally, and the call site in `service.py` drops the outer `to_thread` and just `await`s `resolve()` directly. This is the one structural change beyond "add an adapter" — call it out in review, it's the main risk area.
2. **`StampOcr` contract changes from `read_text(image: PIL.Image) -> str` to `async def read_date(self, content: bytes) -> date | None`.** Takes raw bytes (not a decoded PIL Image) — `HttpStampReader` only needs bytes to POST as multipart, no need to decode-then-reencode. Matches `DetectorClient.detect(image: bytes, ...)`'s existing convention.
3. **`parse_stamp_date()` (regex text→date parser in `date_resolver.py`) is left in place, untouched, with its existing 18 tests.** It becomes unused in the `resolve()` path (the ML service now does calendar-validated parsing and returns an ISO date directly), but it's a small, correct, well-tested pure function — deleting it and its tests is a bigger unilateral cleanup than this ticket asks for. Do not touch it. Do not call it from the new `_extract_stamp_date`.
4. **Image size (open question in the ticket): keep it one image.** `rapidocr-onnxruntime` + deps add ~100MB to `ml`'s image; ticket asks "worth a separate `ml-ocr` image?" — not doing that split now, it's infra scope beyond this ticket. Just add the deps to the existing `ml/Dockerfile`.
5. **Reprocessing (`detect_backlog`) date-fill is scoped narrowly.** Add a date-fill attempt only at the point in the existing loop where a photo's bytes are already fetched from storage for detection (i.e., not for photos already `skipped` because the detector went down) — extending that skip logic further is not this ticket's job.
6. **`HttpStampReader` shares the existing `DetectorHttpClient` (`Scope.APP` `httpx.AsyncClient`) and reuses `DetectorSettings`** for `url`/timeouts/retries (same ML base URL, same knobs) — no new settings class. Only new field: `DetectorSettings.stamp_enabled: bool = False`.

## Global Constraints

- Backend: `uv run pytest -q` must stay green; `ruff check`/`ruff format --check` clean.
- ML: existing tests in `ml/tests/` must stay green.
- `STAMP_ENABLED=false` (default) or ML not configured → behavior identical to today (`NullStampOcr`, upload never fails because of the stamp step).
- No new migration — `Photo.date_source` already supports `"stamp"` (`DateSource.STAMP` already exists in `backend/app/domains/photo/models.py`).

## Review Focus

- `DateResolver.resolve()`'s async refactor: does the call site in `photo/service.py` still behave identically for the channel/EXIF paths (no accidental behavior change beyond adding the stamp step)?
- `HttpStampReader`: does it actually mirror `HttpDetectorClient`'s retry/backoff/budget logic (503 → retry with backoff, other 4xx → no retry, other 5xx/timeout → 1 retry), or did the haiku implementer take a shortcut?
- `DateResolver._extract_stamp_date`: OCR/HTTP exceptions must NOT propagate (existing invariant) — verify the try/except still wraps the awaited call.
- ML `/stamp`: does it apply `exif_transpose` before OCR, matching `/detect`'s `predict_bytes`?
- Does `STAMP_ENABLED=false` genuinely short-circuit to `NullStampOcr` with zero HTTP calls (check the factory function, not just the setting name)?

---

## Task 1 — ML service: `POST /stamp`

**Files:**
- Modify: `ml/tools/read_date_stamp.py` (refactor `read_stamp` to accept an array instead of a `Path`; add thin wrapper)
- Modify: `ml/service/detector.py` or new `ml/service/stamp_reader.py` (lazy-loaded RapidOCR wrapper, mirrors `Detector`)
- Modify: `ml/service/app.py` (new `POST /stamp` route, `/meta` gains `"stamp": true/false`)
- Modify: `ml/requirements.txt` is already correct (`rapidocr-onnxruntime==1.2.3` etc. already listed under `tools/read_date_stamp.py` — just confirm the pinned versions match what you install in the Dockerfile)
- Modify: `ml/Dockerfile` (add `rapidocr-onnxruntime`, `opencv-python-headless`, `numpy` to the pip install layer)
- Test: `ml/tests/test_service.py` (or a new `ml/tests/test_stamp.py`)

### Step 1: Refactor `read_date_stamp.py` to be importable on an in-memory image

Current `read_stamp(path: Path, ocr) -> StampResult` opens the file itself. Split the file-opening from the detection logic:

```python
def read_stamp_array(img: np.ndarray, ocr, *, name: str = "") -> StampResult:
    """Как read_stamp, но принимает уже декодированный RGB-массив (для сервиса)."""
    hits: list[tuple[dt.date, float, str, str]] = []
    for corner, left, right in ROIS:
        roi = _roi(img, left, right)
        for variant_name, variant in _variants(roi):
            det, _ = ocr(variant)
            for text, conf in _join_fragments(det):
                date = _parse(text)
                if date:
                    hits.append((date, conf, f"{corner}:{variant_name}", text))

    if not hits:
        return StampResult(name, None, None, None, 0, None,
                           "штамп не найден или не читается — нужна ручная привязка")

    votes = Counter()
    for date, _, variant, _ in hits:
        votes[date] = len({v for d, _, v, _ in hits if d == date})
    best_date = max(votes, key=lambda d: (votes[d], max(h[1] for h in hits if h[0] == d)))
    best = max((h for h in hits if h[0] == best_date), key=lambda h: h[1])

    note = ""
    if len(votes) > 1:
        other = ", ".join(f"{d.isoformat()}×{c}" for d, c in votes.items() if d != best_date)
        note = f"разногласие гипотез (выбрано ×{votes[best_date]}; также: {other})"
    elif votes[best_date] == 1:
        note = "подтверждено одной гипотезой — проверить вручную"

    return StampResult(name, best_date.isoformat(), round(best[1], 3), best[2],
                       votes[best_date], best[3], note)


def read_stamp(path: Path, ocr) -> StampResult:
    """CLI: читает файл с диска, делегирует read_stamp_array."""
    img = np.asarray(Image.open(path).convert("RGB"))
    return read_stamp_array(img, ocr, name=path.name)


def read_stamp_for_service(image: np.ndarray, ocr) -> dict:
    """Импортируемая функция для сервиса (LCT-13): {date, text, roi}.

    image — уже RGB ndarray, EXIF-транспонированный вызывающей стороной
    (см. service/app.py, как predict_bytes делает это для /detect).
    """
    result = read_stamp_array(image, ocr)
    roi = result.variant.split(":", 1)[0] if result.variant else None
    return {"date": result.date, "text": result.raw, "roi": roi}
```

Keep `main()` unchanged (it already goes through the file-based `read_stamp`, now delegating to `read_stamp_array` — behavior identical, verify with existing manual CLI run if one exists, otherwise trust the delegation).

### Step 2: Lazy-loaded RapidOCR wrapper in the service

Add to `ml/service/detector.py` (same module is fine — it's small, or a new `ml/service/stamp_reader.py`, implementer's call, keep it consistent with `Detector`'s style):

```python
@dataclass
class StampReader:
    """Ленивая загрузка RapidOCR: не грузить веса, пока штамп не нужен."""

    _ocr: Any = field(default=None, init=False, repr=False)

    @property
    def ocr(self):
        if self._ocr is None:
            from rapidocr_onnxruntime import RapidOCR
            self._ocr = RapidOCR()
        return self._ocr

    def warmup(self) -> None:
        import numpy as np
        from tools.read_date_stamp import read_stamp_array
        read_stamp_array(np.zeros((200, 200, 3), dtype="uint8"), self.ocr)

    def read_bytes(self, data: bytes) -> dict:
        from PIL import Image, ImageOps
        from tools.read_date_stamp import read_stamp_for_service
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        img = np.asarray(img.convert("RGB"))
        return read_stamp_for_service(img, self.ocr)
```

Import `numpy as np` and `io` at module top if not already there. `warmup()` is called lazily on first `/stamp` request (NOT in the app's `lifespan`, unlike the YOLO detector — the ticket says "ленивая загрузка и прогрев", and OCR weights are bundled in the pip package already, so cold start is cheap; don't block app startup on it, don't add it to `lifespan`).

### Step 3: `POST /stamp` route + `/meta` flag

In `ml/service/app.py`:

```python
_stamp_reader: StampReader | None = None


def stamp_reader() -> StampReader:
    global _stamp_reader
    if _stamp_reader is None:
        _stamp_reader = StampReader()
    return _stamp_reader


class StampResponse(BaseModel):
    date: str | None
    text: str | None
    roi: str | None


@app.post("/stamp", response_model=StampResponse, summary="Дата, впечатанная в кадр")
async def stamp(file: UploadFile = File(description="снимок площадки")) -> StampResponse:
    data = await file.read()
    if not data:
        raise HTTPException(400, "пустой файл")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, f"файл больше {MAX_BYTES // 1048576} МБ")
    try:
        result = stamp_reader().read_bytes(data)
    except Exception as exc:
        raise HTTPException(422, f"не удалось обработать кадр: {exc}") from exc
    return StampResponse(**result)
```

Update `meta()`:

```python
@app.get("/meta", summary="Чем именно отвечает сервис")
def meta() -> dict:
    return {**detector().meta(), "stamp": True}
```

(`stamp: true` is unconditional — the OCR path has no separate on/off switch on the ML side, only the backend's `DETECTOR__STAMP_ENABLED` gates whether it's *called*.)

### Step 4: Dockerfile + requirements

Add to the single `pip install --no-cache-dir` layer in `ml/Dockerfile`:
```
opencv-python-headless==5.0.0.93 numpy==2.5.2 rapidocr-onnxruntime==1.2.3
```
(exact pins from `ml/requirements.txt`, which already lists them under the `tools/read_date_stamp.py` comment).

### Step 5: Tests

`ml/tests/test_service.py` (or new file): `TestClient(app)`, at least:
- `POST /stamp` with a synthetic frame that has no stamp → `{"date": None, ...}`, 200.
- `POST /stamp` with an empty file → 400.
- `POST /stamp` with oversized file → 413.
- `GET /meta` → `"stamp": True` present.

If there's an existing fixture image with a real stamp under `ml/data/reference` or `ml/tests/fixtures`, add one positive case asserting `date` is a valid ISO string. If none exists in the test fixtures already, a synthetic case is enough — don't go fetch/generate new binary fixtures for this, out of scope.

---

## Task 2 — Backend: `HttpStampReader`, `DateResolver` async refactor, DI, settings

**Files:**
- Modify: `backend/app/core/settings.py` (`DetectorSettings.stamp_enabled`)
- New: `backend/app/adapters/ml/stamp.py` (`HttpStampReader`)
- Modify: `backend/app/adapters/ml/factory.py` (`create_stamp_reader`)
- Modify: `backend/app/domains/photo/date_resolver.py` (`StampOcr` contract, `NullStampOcr`, async `resolve()`)
- Modify: `backend/app/domains/photo/provider.py` (wire `create_stamp_reader`)
- Modify: `backend/app/domains/photo/service.py` (drop `to_thread` around `resolve()`; date-fill in `detect_backlog`)
- Modify: `.env.dist` (document `DETECTOR__STAMP_ENABLED`)
- Test: `backend/tests/test_ml_adapter.py` (or new `test_stamp_adapter.py`) — `httpx.MockTransport`
- Test: `backend/tests/test_photo_date_resolver.py` — fake async `StampOcr`, verify `resolve()` returns `DateSource.STAMP` correctly and that OCR exceptions don't propagate
- Test: `backend/tests/test_photo_service.py` — `detect_backlog` date-fill (if a suitable existing test class exists, extend it)

### Step 1: Settings

In `backend/app/core/settings.py`, `DetectorSettings`:
```python
class DetectorSettings(BaseModel):
    """Параметры ML-детектора."""

    url: str | None = None
    timeout_s: float = 30.0
    connect_timeout_s: float = 2.0
    max_concurrency: int = 2
    retry_503: int = 3
    retry_other: int = 1
    retry_backoff_s: tuple[float, ...] = (2.0, 5.0, 10.0)
    retry_budget_s: float = 20.0
    stamp_enabled: bool = False  # LCT-13
```

### Step 2: `StampOcr` contract + `NullStampOcr` + async `resolve()`

In `backend/app/domains/photo/date_resolver.py`:

```python
class StampOcr(Protocol):
    """Протокол чтения даты со штампа на кадре (LCT-13: через ML-сервис)."""

    async def read_date(self, content: bytes) -> date | None:
        """Прочитать дату со штампа. Возвращает None, если штамп не найден
        или не прошёл проверку — это не ошибка."""
        ...


class NullStampOcr:
    """Заглушка: штамп никогда не читается."""

    async def read_date(self, content: bytes) -> date | None:
        return None
```

`DateResolver` — `resolve()` becomes async, image opening moves into a thread internally, stamp step awaits the new contract:

```python
class DateResolver:
    def __init__(self, ocr: StampOcr | None = None) -> None:
        self.ocr = ocr if ocr is not None else NullStampOcr()

    async def resolve(self, content: bytes, channel_date: date | None = None) -> ResolvedDate:
        if channel_date is not None:
            return ResolvedDate(captured_on=channel_date, source=DateSource.CHANNEL)

        try:
            image = await asyncio.to_thread(self._open_image, content)
        except (OSError, Image.UnidentifiedImageError) as e:
            raise InvalidImageError(f"Failed to read image: {e}") from e
        except InvalidImageError:
            raise
        except Exception as e:
            raise InvalidImageError(f"Invalid or corrupt image: {e}") from e

        exif_date = self._extract_exif_date(image)
        if exif_date is not None:
            return ResolvedDate(captured_on=exif_date, source=DateSource.METADATA)

        stamp_date = await self._extract_stamp_date(content)
        if stamp_date is not None:
            return ResolvedDate(captured_on=stamp_date, source=DateSource.STAMP)

        return ResolvedDate(captured_on=None, source=None)

    @staticmethod
    def _open_image(content: bytes) -> Image.Image:
        image = Image.open(BytesIO(content))
        image.load()
        return image

    # _extract_exif_date, _parse_exif_datetime: UNCHANGED, still sync (fast, no I/O)

    async def _extract_stamp_date(self, content: bytes) -> date | None:
        """Извлечь дату через OCR-адаптер. Исключения НЕ распространяются
        (as before) — сеть/ML-сервис недоступен -> просто нет даты со штампа."""
        try:
            return await self.ocr.read_date(content)
        except Exception:
            return None
```

Note `_extract_stamp_date` now takes raw `content: bytes` (the original upload bytes), not the already-opened `Image.Image` — because `StampOcr.read_date` takes bytes now (Ruling #2). Don't re-encode the PIL image back to bytes; just pass the original `content` through unchanged — it's already sitting in scope in `resolve()`.

Add `import asyncio` at the top of the file if not already imported.

`parse_stamp_date` stays exactly as-is (Ruling #3) — just unused from `resolve()`'s new path.

### Step 3: `HttpStampReader`

New file `backend/app/adapters/ml/stamp.py`. Mirror `HttpDetectorClient`'s retry/backoff/budget structure from `backend/app/adapters/ml/http.py` (same `_wait_before_retry` shape, same semaphore-per-instance pattern is optional here — the shared client already has `DetectorSettings.max_concurrency` applied by `HttpDetectorClient`'s own semaphore for `/detect`; `HttpStampReader` can use its own `asyncio.Semaphore(settings.max_concurrency)` too, same knob, separate counter since it's a separate instance):

```python
"""HTTP-клиент для чтения даты со штампа через ML-сервис (LCT-13).

Контракт: POST {base}/stamp, multipart/form-data, поле `file`.
Ответ: {"date": "2024-04-24" | null, "text": "...", "roi": "right"|"left"|null}.
Ошибки как у /detect: 400/413/422 не повторяются, 503 — retry с backoff.
"""

import asyncio
import logging
from datetime import date

import httpx
from pydantic import BaseModel

from app.core.settings import DetectorSettings

logger = logging.getLogger(__name__)


class _StampSchema(BaseModel):
    date: str | None = None
    text: str | None = None
    roi: str | None = None

    model_config = {"extra": "ignore"}


class HttpStampReader:
    """StampOcr через HTTP ML-сервис. Тот же base_url, что у детектора."""

    def __init__(
        self,
        base_url: str,
        client: httpx.AsyncClient,
        settings: DetectorSettings,
        sleep=asyncio.sleep,
    ) -> None:
        self.base_url = base_url
        self.client = client
        self.settings = settings
        self._sleep = sleep
        self._semaphore = asyncio.Semaphore(settings.max_concurrency)

    async def _wait_before_retry(self, attempt: int, spent: float) -> float | None:
        backoff_index = min(attempt - 1, len(self.settings.retry_backoff_s) - 1)
        sleep_time = self.settings.retry_backoff_s[backoff_index]
        if spent + sleep_time <= self.settings.retry_budget_s:
            await self._sleep(sleep_time)
            return spent + sleep_time
        return None

    async def read_date(self, content: bytes) -> date | None:
        url = f"{self.base_url}/stamp"
        timeout = httpx.Timeout(self.settings.timeout_s, connect=self.settings.connect_timeout_s)

        retry_503_count = 0
        retry_other_count = 0
        total_sleep = 0.0

        while True:
            try:
                async with self._semaphore:
                    response = await self.client.post(
                        url,
                        files={"file": ("upload", content, None)},
                        timeout=timeout,
                    )

                if response.status_code == 503:
                    if retry_503_count < self.settings.retry_503:
                        retry_503_count += 1
                        new_spent = await self._wait_before_retry(retry_503_count, total_sleep)
                        if new_spent is not None:
                            total_sleep = new_spent
                            continue
                    logger.warning("Stamp service 503, retries exhausted")
                    return None

                if 400 <= response.status_code < 500:
                    logger.warning("Stamp service HTTP %d, no retry", response.status_code)
                    return None

                if response.status_code >= 500:
                    if retry_other_count < self.settings.retry_other:
                        retry_other_count += 1
                        new_spent = await self._wait_before_retry(retry_other_count, total_sleep)
                        if new_spent is not None:
                            total_sleep = new_spent
                            continue
                    logger.warning("Stamp service HTTP %d, retries exhausted", response.status_code)
                    return None

                if response.status_code == 200:
                    try:
                        data = response.json()
                        parsed = _StampSchema(**data)
                    except Exception:
                        logger.warning("Stamp service: invalid response body")
                        return None
                    if not parsed.date:
                        return None
                    try:
                        return date.fromisoformat(parsed.date)
                    except ValueError:
                        logger.warning("Stamp service returned unparseable date: %r", parsed.date)
                        return None

                logger.warning("Stamp service unexpected HTTP %d", response.status_code)
                return None

            except httpx.TimeoutException:
                if retry_other_count < self.settings.retry_other:
                    retry_other_count += 1
                    new_spent = await self._wait_before_retry(retry_other_count, total_sleep)
                    if new_spent is not None:
                        total_sleep = new_spent
                        continue
                logger.warning("Stamp service timeout, retries exhausted")
                return None
            except httpx.TransportError:
                if retry_other_count < self.settings.retry_other:
                    retry_other_count += 1
                    new_spent = await self._wait_before_retry(retry_other_count, total_sleep)
                    if new_spent is not None:
                        total_sleep = new_spent
                        continue
                logger.warning("Stamp service connection error, retries exhausted")
                return None
```

Note the deliberate difference from `HttpDetectorClient.detect()`: that one *raises* `DetectorError` on unrecoverable failure (the domain needs to know detection failed vs. "detector off"). `HttpStampReader.read_date()` instead *returns `None`* on any unrecoverable failure — because `StampOcr`'s whole contract is "date or no date, never an error" (Ruling: matches `_extract_stamp_date`'s existing try/except-everything invariant; returning `None` here rather than raising is simpler than raising-then-catching one level up, and keeps `HttpStampReader` a drop-in for `NullStampOcr`).

`base_url` here should already be the normalized URL (no `/detect` suffix) — reuse `normalize_base_url` from `app/adapters/ml/http.py` when constructing it in the factory, don't reimplement it.

### Step 4: Factory + DI wiring

In `backend/app/adapters/ml/factory.py`, add:
```python
from app.adapters.ml.stamp import HttpStampReader
from app.domains.photo.date_resolver import NullStampOcr, StampOcr


def create_stamp_reader(
    settings: Settings,
    client: httpx.AsyncClient | None,
) -> StampOcr:
    """NullStampOcr если STAMP_ENABLED=false, URL пустой, или клиент недоступен."""
    if (
        settings.detector.stamp_enabled
        and settings.detector.url
        and settings.detector.url.strip()
        and client is not None
    ):
        return HttpStampReader(
            base_url=normalize_base_url(settings.detector.url),
            client=client,
            settings=settings.detector,
        )
    return NullStampOcr()
```
(Import `normalize_base_url` from `app.adapters.ml.http` at the top of `factory.py`.)

In `backend/app/domains/photo/provider.py`, replace the hardcoded stub:
```python
@provide(scope=Scope.APP)
def stamp_ocr(self, settings: Settings, client: DetectorHttpClient) -> StampOcr:
    return create_stamp_reader(settings, client)
```
(Check the exact existing `detector` provider method just above it for how it already gets `settings`/`client` typed — e.g. `client: DetectorHttpClient | None` — mirror that exactly, don't guess the type.)

### Step 5: `photo/service.py` call site + `detect_backlog` date-fill

Change:
```python
resolved_date = await asyncio.to_thread(self._resolver.resolve, file_input.content)
```
to:
```python
resolved_date = await self._resolver.resolve(file_input.content)
```
(same `try: ... except InvalidImageError:` wrapper around it, unchanged).

In `detect_backlog` (around line 658-666), right after `content = await self._storage.get(photo.storage_key)` succeeds, before the detection try/except, add (only if the photo currently has no date):
```python
if photo.captured_on is None:
    try:
        resolved = await self._resolver.resolve(content)
    except InvalidImageError:
        resolved = None
    if resolved is not None and resolved.captured_on is not None:
        photo.captured_on = resolved.captured_on
        photo.date_source = resolved.source.value if resolved.source else None
```
This commits together with the rest of that iteration's existing `await self._session.commit()` calls (don't add a new commit here).

### Step 6: Tests

`test_ml_adapter.py` or new `test_stamp_adapter.py`: `httpx.MockTransport`-based, mirroring however `HttpDetectorClient` is tested currently (read that file's existing patterns first) —
- 200 with a date → returns the parsed `date`.
- 200 with `date: null` → returns `None`.
- 422 → returns `None`, no retry (assert transport call count == 1).
- 503 then 200 → returns the date after one retry (assert `sleep` was called, via injected fake `sleep`).
- 503 exhausted → returns `None`.
- Malformed JSON body → returns `None`, no exception raised.

`test_photo_date_resolver.py`: add a fake async `StampOcr` (`class _FakeAsyncOcr: async def read_date(self, content): return self._date`) and:
- `resolve()` with no channel date, no EXIF, fake OCR returns a date → `ResolvedDate(date, DateSource.STAMP)`.
- Fake OCR raises → `resolve()` still returns a result with `source=None` (doesn't propagate).
- Existing EXIF-priority tests: verify they still pass with `resolve()` now async (just add `await`/`pytest.mark.asyncio` to the existing test functions calling `resolve()` — check `test_resolved_date_with_both_set` etc. for exactly which tests call `.resolve()` vs. just construct `ResolvedDate`, only the former need updating).

`test_photo_service.py`: extend an existing `detect_backlog` test (or add one) with a photo that has `captured_on=None` and a resolver that returns a stamp date — assert it gets filled in and `date_source == "stamp"`.

---

## Definition of Done (from the ticket, unchanged)

- `STAMP_ENABLED=false` or ML off → upload behaves exactly as before, never fails because of the stamp step.
- With `STAMP_ENABLED=true` and ML running, a frame with a stamp gets `date_source=stamp` and the right date.
- Full backend suite green, full `ml/tests` green, ruff clean.
