class Message:
    """ Simple wrapper for a message. Note that ALL fields may be None! """
    def __init__(self, sender, recipient, subject, body):
        self.sender = sender
        self.recipient = recipient
        self.subject = subject
        self.body = body

    def is_valid(self):
        return self.sender and self.recipient and self.body

    def is_empty(self):
        return not (self.sender or self.recipient or self.body)

    def __str__(self):
        return "f='%s' t='%s' s='%s' b='%s'" % (self.sender,
                                               self.recipient,
                                               self.subject,
                                               self.body)
