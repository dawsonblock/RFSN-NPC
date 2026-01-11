import time
import threading
from rfsn_hybrid.core.queues import BoundedQueue, DropPolicy

def test_queue_overflow_block():
    """
    Verify BoundedQueue with DropPolicy.BLOCK never exceeds maxsize.
    Scenario: 2 aggressive producers, 1 slow consumer.
    """
    q = BoundedQueue[int](maxsize=3, drop_policy=DropPolicy.BLOCK)
    stop_event = threading.Event()
    
    def producer():
        i = 0
        while not stop_event.is_set():
            q.put(i, timeout=0.01)
            i += 1
            
    def slow_consumer():
        while not stop_event.is_set():
            time.sleep(0.02)
            q.get(timeout=0.01)

    t_prod1 = threading.Thread(target=producer)
    t_prod2 = threading.Thread(target=producer)
    t_cons = threading.Thread(target=slow_consumer)
    
    t_prod1.start()
    t_prod2.start()
    t_cons.start()
    
    # Check size constraint repeatedly
    errors = []
    for _ in range(50):
        size = q.size() if hasattr(q, "size") else len(q._queue)
        if size > 3:
            errors.append(size)
        time.sleep(0.01)
        
    stop_event.set()
    t_prod1.join()
    t_prod2.join()
    t_cons.join()
    
    assert not errors, f"Queue exceeded maxsize (3). Observed sizes: {errors}"
