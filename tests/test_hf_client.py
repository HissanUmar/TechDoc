from agentic_framework.hf_client import HfClient


def test_hf_client_stub():
    # Without token, client should fallback to stub (gpt2)
    client = HfClient(model="mistralai/Mistral-7B-Instruct-v0.1", token=None)
    out = client.call_model("hello world")
    # Should fall back to gpt2 stub since no token provided
    assert out["model"] == "gpt2"
    assert out["status"] == "stub"
    assert "ECHO: hello world" in out["output"]
