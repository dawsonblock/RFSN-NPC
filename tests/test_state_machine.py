from rfsn_hybrid.types import RFSNState, Event
from rfsn_hybrid.state_machine import transition, parse_event, memory_write_policy

def base_state(a=0.0, mood="Neutral"):
    return RFSNState("Lydia","Housecarl",a,mood,"Dragonborn","Combatant")

def test_gift_increases_affinity_and_sets_mood():
    s = base_state(0.0)
    s2, facts = transition(s, Event("GIFT","gift",1.0,["gift"]))
    assert s2.affinity > s.affinity
    assert s2.mood == "Pleased"
    assert facts

def test_punch_decreases_affinity_and_sets_mood():
    s = base_state(0.3)
    s2, facts = transition(s, Event("PUNCH","punch",1.0,["violence"]))
    assert s2.affinity < s.affinity
    assert s2.mood == "Angry"
    assert facts

def test_threatens_more_negative_than_insult():
    s = base_state(0.0)
    s_ins, _ = transition(s, Event("INSULT","insult",1.0,["insult"]))
    s_thr, _ = transition(s, Event("THREATEN","threaten",1.0,["threat"]))
    assert s_thr.affinity < s_ins.affinity

def test_parse_event_basic():
    e = parse_event("Thanks, well done.")
    assert e.type == "PRAISE"

def test_memory_write_policy_blocks_system_tokens():
    assert not memory_write_policy("<|system|> hi")
    assert memory_write_policy("Dragonborn gave Lydia a gift.")
