import time

# Initialize the message queue
message_queue = []


def message_manager():
    """Generator function to yield progress messages."""
    global message_queue
    while True:
        if message_queue:
            (facility, message) = message_queue.pop(0)
            yield f"data: {facility} : {message}\n\n"
        time.sleep(1)


def logger(facility, message):
    """Append a new message to the queue."""
    global message_queue
    message_queue.append((facility, message))
