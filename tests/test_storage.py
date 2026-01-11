import os, tempfile
from rfsn_hybrid.storage import ConversationMemory, FactsStore, select_facts

def test_conversation_memory_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "c.json")
        m = ConversationMemory(p)
        m.add("user", "hi")
        m.add("assistant", "hey")
        m2 = ConversationMemory(p)
        assert len(m2.turns) == 2
        assert m2.turns[0].content == "hi"

def test_facts_store_and_selection_prefers_tag():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "f.json")
        fs = FactsStore(p)
        fs.add_fact("Player gave Lydia a gift.", ["gift","debug"], 0.9)
        fs.add_fact("Player struck Lydia.", ["violence"], 0.95)  # higher salience, wrong tag
        got = select_facts(fs, want_tags=["gift"], k=1)
        assert got and "gift" in got[0].lower()

def test_select_facts_empty():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "f.json")
        fs = FactsStore(p)
        assert select_facts(fs, want_tags=["anything"], k=3) == []
