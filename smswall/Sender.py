import logging

class Sender:
    def send_sms(self, sender, receipient, subject, data):
        raise NotImplementedError

class TestSender(Sender):
    """ Saves output to an easily parse-able file format to allow automated
    verification.
    """

    def __init__(self):
        self.msg_count = 0
        self.logger = logging.getLogger("testsender")
    def send_sms(self, sender, recipient, subject, data):
        msg = [ self.msg_count, sender, recipient, subject, data ]
        self.logger.info("%s" % msg)
        self.msg_count += 1


class LogSender(Sender):
    def send_sms(self, sender, recipient, subject, data):
        logging.basicConfig(level=logging.DEBUG)
        logging.info("Sent SMS. From: '%s' To: '%s' Subj: '%s' Message: '%s'" \
                     % (sender, recipient, subject, data))
        return True
