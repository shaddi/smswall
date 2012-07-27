import logging

class Sender:
    def send_sms(sender, receipient, subject, data):
        raise NotImplementedError

class LogSender(Sender):
    def send_sms(sender, recipient, subject, data):
        logging.basicConfig(level=logging.DEBUG)
        logging.info("Sent SMS. From: '%s' To: '%s' Subj: '%s' Message: '%s'" \
                     % (sender, recipient, subject, data))
        return True
