from __future__ import annotations

import os
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Model fallback chain: primary first, then fallbacks
MODEL_CHAIN = [
    "mistralai/Mistral-7B-Instruct-v0.1",  # Primary: best reasoning
    "meta-llama/Llama-2-7b-chat-hf",       # Fallback 1: conversational
    "tiiuae/falcon-7b-instruct",           # Fallback 2: fast
    "google/flan-t5-large",                # Fallback 3: structured NLU
    "gpt2",                                 # Final fallback: stub
]


class HfClient:
    """Hugging Face client wrapper with automatic model fallback.

    Tries to use `huggingface_hub.InferenceApi` with a fallback chain of models.
    If a model fails to load or returns an error, automatically tries the next model
    in the chain. Tracks which model is actually in use for transparency.
    """

    def __init__(
        self,
        model: str | None = None,
        token: str | None = None,
        model_chain: List[str] | None = None,
    ) -> None:
        self.requested_model = model or MODEL_CHAIN[0]
        self.model = None  # Will be set to the actual working model
        self.token = token or os.environ.get("HF_API_TOKEN")
        self._client = None
        self.model_chain = model_chain or MODEL_CHAIN
        self.attempted_models: Dict[str, str] = {}  # Track attempts and errors

        # Try to load a model from the chain
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Try to initialize client with models in the fallback chain."""
        try:
            from huggingface_hub import InferenceApi  # type: ignore

            if not self.token:
                logger.warning("HF token not found; falling back to stub client")
                self.model = "gpt2"
                return

            # Try each model in the chain
            for model_name in self.model_chain:
                try:
                    test_client = InferenceApi(repo_id=model_name, token=self.token)
                    self._client = test_client
                    self.model = model_name
                    logger.info(
                        "✅ Successfully loaded model: %s (requested: %s)",
                        model_name,
                        self.requested_model,
                    )
                    self.attempted_models[model_name] = "success"
                    return
                except Exception as e:
                    error_msg = str(e)[:100]
                    self.attempted_models[model_name] = error_msg
                    logger.debug(
                        "⚠️ Model %s failed (%s), trying next...", model_name, error_msg
                    )
                    continue

            # All models failed, use stub
            logger.warning("All HF models failed; using stub client")
            self.model = "gpt2"

        except Exception:  # pragma: no cover
            logger.info("huggingface_hub not available; using stub client")
            self.model = "gpt2"

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

                return {
                    "model": self.model,
                    "output": out,
                    "raw": resp,
                    "status": "success",
                }
            except Exception as e:
                logger.exception("Error calling HF InferenceApi: %s", e)
                # fallback to stub behavior on error

        # stub echo response
        return {
            "model": self.model,
            "output": f"ECHO: {prompt}",
            "raw": None,
            "status": "stub" if self.model == "gpt2" else "fallback",
        }

    def get_status(self) -> Dict[str, Any]:
        """Get current model status and attempted models."""
        return {
            "requested_model": self.requested_model,
            "active_model": self.model,
            "has_token": bool(self.token),
            "client_available": self._client is not None,
            "attempted_models": self.attempted_models,
        }
