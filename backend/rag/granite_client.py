"""
watsonx.ai inference client for OrbitLens.

Model:   ibm/granite-4-h-small
Region:  us-south (https://us-south.ml.cloud.ibm.com)

Returns None when credentials are not configured or the call fails/times out.
Callers must handle None with a context-aware fallback.
"""

from __future__ import annotations

import os
import warnings

warnings.filterwarnings("ignore")

# Hard timeout (seconds) for each watsonx.ai call so a stalled connection
# never hangs the event loop or the thread indefinitely.
_WATSONX_TIMEOUT_SECONDS: int = int(os.getenv("WATSONX_TIMEOUT_SECONDS", "30"))

# Module-level model cache — built once, reused for every call.
_cached_model = None
_cached_creds_key: tuple[str, str, str] | None = None


def _get_model():
    """Return a cached ModelInference instance, creating it on first call."""
    global _cached_model, _cached_creds_key  # noqa: PLW0603

    api_key    = os.getenv("WATSONX_APIKEY", "").strip()
    project_id = os.getenv("WATSONX_PROJECT_ID", "").strip()
    url        = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com").strip()

    if not (api_key and project_id):
        return None

    creds_key = (api_key, project_id, url)
    if _cached_model is not None and _cached_creds_key == creds_key:
        return _cached_model

    from ibm_watsonx_ai import Credentials
    from ibm_watsonx_ai.foundation_models import ModelInference

    credentials = Credentials(url=url, api_key=api_key)
    _cached_model = ModelInference(
        model_id="ibm/granite-4-h-small",
        credentials=credentials,
        project_id=project_id,
        params={"max_new_tokens": 300, "temperature": 0.1},
    )
    _cached_creds_key = creds_key
    return _cached_model


def query_granite(prompt: str) -> str | None:
    """
    Send `prompt` to watsonx.ai and return the generated text.

    - Enforces a hard _WATSONX_TIMEOUT_SECONDS timeout via a daemon thread.
    - Returns None on missing credentials, timeout, or any API failure.
    - Safe to call from both sync and async contexts.
    """
    import concurrent.futures

    try:
        model = _get_model()
    except Exception as exc:  # noqa: BLE001
        print(f"[OrbitLens RAG] watsonx.ai model init error: {exc}")
        return None

    if model is None:
        return None

    def _call() -> str | None:
        try:
            result = model.generate_text(prompt=prompt)
            if isinstance(result, str):
                return result.strip() or None
            return str(result).strip() or None
        except Exception as exc:  # noqa: BLE001
            print(f"[OrbitLens RAG] watsonx.ai generate error: {exc}")
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_call)
        try:
            return future.result(timeout=_WATSONX_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            print(f"[OrbitLens RAG] watsonx.ai call timed out after {_WATSONX_TIMEOUT_SECONDS}s — using fallback.")
            return None
        except Exception as exc:  # noqa: BLE001
            print(f"[OrbitLens RAG] watsonx.ai unexpected error: {exc}")
            return None
