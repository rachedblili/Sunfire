import time
import sys
from queue import Queue
# Initialize the message queue
message_queue = Queue()


def message_manager():
    """
    Generates a message manager that continuously yields messages from the message queue.

    This function uses a global message queue to retrieve messages and yields them in a specific format.
    The yielded messages consist of the session ID, facility, and message separated by colons.
    If the message queue is empty, the function checks if a certain count has been reached.
    If the count is greater than or equal to 10, it yields a keepalive message and resets the count.
    The function sleeps for 1 second between each iteration.

    Returns:
        Generator: A generator that yields messages in the format "data: session_id : facility : message\n\n".
    """
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
