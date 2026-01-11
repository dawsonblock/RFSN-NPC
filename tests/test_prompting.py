from rfsn_hybrid.prompting import render_llama3, render_phi3_chatml, default_template_for_model, stop_tokens_for_template
from rfsn_hybrid.storage import Turn

def test_default_template_llama3():
    assert default_template_for_model("Mantella-Skyrim-Llama-3-8B-Q4_K_M.gguf") == "llama3"

def test_default_template_phi3():
    assert default_template_for_model("phi-3-mini-4k-instruct.Q4_K_M.gguf") == "phi3_chatml"

def test_stop_tokens():
    assert stop_tokens_for_template("llama3") == ["<|eot_id|>"]
    assert stop_tokens_for_template("phi3_chatml") == ["<|end|>"]

def test_render_llama3_contains_headers():
    hist = [Turn(role="user", content="hi", time="t"), Turn(role="assistant", content="hello", time="t")]
    p = render_llama3("sys", hist, "user says")
    assert "<|start_header_id|>system" in p
    assert "<|start_header_id|>user" in p
    assert "<|start_header_id|>assistant" in p
    assert "sys" in p and "user says" in p

def test_render_phi3_contains_tags():
    hist = [Turn(role="user", content="hi", time="t")]
    p = render_phi3_chatml("sys", hist, "yo")
    assert "<|system|>" in p
    assert "<|user|>" in p
    assert "<|assistant|>" in p
