import os
from agentic_framework.hf_client import HfClient
from dotenv import load_dotenv


load_dotenv()  # Load environment variables from .env file for testing

def test_hf_client_stub():
    # Without token, client should use requested model name but return stub
    client = HfClient(model="mistralai/Mistral-7B-Instruct-v0.1", token=os.getenv("HF_API_TOKEN"))
    out = client.call_model("hello world")
    # Active model is the requested one, but response is a local stub
    assert out["model"] == "mistralai/Mistral-7B-Instruct-v0.1"
    assert out["status"] == "stub"
    assert "ECHO: hello world" in out["output"]
