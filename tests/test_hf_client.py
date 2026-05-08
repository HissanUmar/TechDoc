from agentic_framework.hf_client import HfClient


def test_hf_client_stub():
    # Without installing huggingface_hub or providing a token, client should fallback to stub
    client = HfClient(model="test-model", token=None)
    out = client.call_model("hello world")
    assert out["model"] == "test-model"
    assert "ECHO: hello world" in out["output"]
