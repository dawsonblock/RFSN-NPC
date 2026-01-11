from __future__ import annotations
from typing import List, Literal
from .storage import Turn

PromptTemplate = Literal["llama3", "phi3_chatml"]

def render_llama3(system_text: str, history: List[Turn], user_text: str) -> str:
    parts: List[str] = []
    parts.append("<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n")
    parts.append(system_text.strip() + "\n<|eot_id|>")
    for t in history:
        header = "user" if t.role == "user" else "assistant"
        parts.append(f"<|start_header_id|>{header}<|end_header_id|>\n\n")
        parts.append(t.content.strip() + "\n<|eot_id|>")
    parts.append("<|start_header_id|>user<|end_header_id|>\n\n")
    parts.append(user_text.strip() + "\n<|eot_id|>")
    parts.append("<|start_header_id|>assistant<|end_header_id|>\n\n")
    return "".join(parts)

def render_phi3_chatml(system_text: str, history: List[Turn], user_text: str) -> str:
    parts: List[str] = []
    parts.append(f"<|system|>{system_text.strip()}<|end|>\n")
    for t in history:
        tag = "<|user|>" if t.role == "user" else "<|assistant|>"
        parts.append(f"{tag}{t.content.strip()}<|end|>\n")
    parts.append(f"<|user|>{user_text.strip()}<|end|>\n<|assistant|>")
    return "".join(parts)

def default_template_for_model(model_path: str) -> PromptTemplate:
    p = model_path.lower()
    if "llama-3" in p or "mantella" in p:
        return "llama3"
    if "phi-3" in p or "phi3" in p:
        return "phi3_chatml"
    return "llama3"

def stop_tokens_for_template(tpl: PromptTemplate) -> List[str]:
    return ["<|eot_id|>"] if tpl == "llama3" else ["<|end|>"]
