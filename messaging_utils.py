import time
from queue import Queue
# Initialize the message queue
message_queue = Queue()


def message_manager():
    """Generator function to yield progress messages."""
    global message_queue
    while True:
        if not message_queue.empty():
            session_id, facility, message = message_queue.get()
            yield f"data: {session_id} : {facility} : {message}\n\n"
        time.sleep(1)


def logger(session_id, facility, message):
    """Append a new message to the queue."""
    global message_queue
    message_queue.put((session_id, facility, message))
