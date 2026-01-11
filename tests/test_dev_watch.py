import os, tempfile, time
from rfsn_hybrid.dev_watch import DevWatch

def test_dev_watch_detects_edit():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.py")
        with open(p, "w", encoding="utf-8") as f:
            f.write("x=1\n")
        w = DevWatch([d])
        time.sleep(0.02)
        with open(p, "w", encoding="utf-8") as f:
            f.write("x=2\n")
        changed = w.check()
        assert any(c.endswith("a.py") for c in changed)
