class BufferedPrint:
    """A class that buffers print messages and prints them all at once when flush is
    called.

    Examples
    --------
    # Create a BufferedPrint object
    >>> message_buffer = BufferedPrint()
    # Redirect print to the BufferedPrint object
    >>> print("Some message", file=message_buffer)
    # Flush the buffered messages and print them
    >>> message_buffer.flush()
    """

    def __init__(self):
        self.messages = []

    def write(self, message):
        self.messages.append(message)

    def flush(self):
        # Process the buffered messages
        for message in self.messages:
            print(message, end="")

        # Clear the buffered messages
        self.messages = []
