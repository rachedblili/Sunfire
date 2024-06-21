import time
import sys
from queue import Queue
# Initialize the message queue
message_queue = Queue()


def message_manager():
    """Generator function to yield progress messages."""
    global message_queue
    count = 0
    while True:
        if not message_queue.empty():
            session_id, facility, message = message_queue.get()
            yield f"data: {session_id} : {facility} : {message}\n\n"
            sys.stdout.flush()
        elif count >= 10:
            yield f"data: xxx : keepalive : ping\n\n"
            sys.stdout.flush()
            count = 0
        count += 1
        time.sleep(1)


def logger(session_id, facility, message):
    """Append a new message to the queue."""
    global message_queue
    message_queue.put((session_id, facility, message))
