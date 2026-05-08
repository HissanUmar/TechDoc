from __future__ import annotations

import os
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class HfClient:
    """Hugging Face client wrapper.

    Tries to use `huggingface_hub.InferenceApi` when available and an API token
    is present in the environment (`HF_API_TOKEN`). If unavailable, falls back
    to a local stub that echoes prompts. This keeps tests and local development
    working without requiring the HF SDK.
    """

    def __init__(self, model: str = "gpt2", token: str | None = None) -> None:
        self.model = model
        self.token = token or os.environ.get("HF_API_TOKEN")
        self._client = None

        try:
            from huggingface_hub import InferenceApi  # type: ignore

            if self.token:
                self._client = InferenceApi(repo_id=self.model, token=self.token)
                logger.info("Using huggingface_hub InferenceApi for model %s", self.model)
            else:
                logger.warning("HF token not found; falling back to stub client")
        except Exception:  # pragma: no cover - import dependency may not be present
            logger.info("huggingface_hub not available; using stub client")

    def call_model(self, prompt: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Call the model. Returns a dict with at least `model` and `output`.

        When using the HF Inference API, the return value is normalized into
        this dict shape. When the SDK isn't available, a local echo stub is used.
        """
        params = params or {}

        if self._client is not None:
            try:
                # InferenceApi returns string or complex types depending on model
                resp = self._client(inputs=prompt, parameters=params)
                # normalize response
                if isinstance(resp, (str, bytes)):
                    out = resp if isinstance(resp, str) else resp.decode("utf-8")
                elif isinstance(resp, dict) and "generated_text" in resp:
                    out = resp["generated_text"]
                elif isinstance(resp, list) and len(resp) > 0 and isinstance(resp[0], dict):
                    # e.g., some models return tokens or structured responses
                    out = resp[0].get("generated_text", str(resp))
                else:
                    out = str(resp)

                return {"model": self.model, "output": out, "raw": resp}
            except Exception as e:
                logger.exception("Error calling HF InferenceApi: %s", e)
                # fallback to stub behavior on error

        # stub echo response
        return {"model": self.model, "output": f"ECHO: {prompt}", "raw": None}
