import logging
import sqlite3
import yaml

class List:
    """ This class is a wrapper around all the list-centric commands. """
    def __init__(self, shortcode, app):
        self.shortcode = shortcode
        self.app = app # the SMSWall app that made this List object
        self.conf = app.conf
        self.db = self.conf.db

    def create(self):
        if not app.is_valid_shortcode(self.shortcode):
            app.reply("The shortcode you selected is invalid. Please choose a" +
                      + "number between %d and %d." % (self.conf.min_shortcode, \
                                                       self.conf.max_shortcode))
        elif len(self.db.execute("SELECT * FROM lists WHERE shortcode=?", \
                               self.shortcode)):
            app.reply("The shortcode '%s' is already in use.")
        else:
            self.conf.log.info("Creating list %s" % self.shortcode)
            # TODO: DB

    def delete(self, confirmed=False):
        """ If confirmed, remove list from list table, then all associated
        members. Otherwise, save message in confirm_action table.
        """
        raise NotImplementedError

    def add_user(self, number):
        raise NotImplementedError

    def delete_user(self, number):
        raise NotImplementedError

    def make_owner(self, number):
        raise NotImplementedError

    def unmake_owner(self, number):
        raise NotImplementedError

    def post(self, sender, message):
        raise NotImplementedError

class Message:
    """ Simple wrapper for a message. Note that ALL fields may be None! """
    def __init__(self, sender, recipient, subject, body):
        self.sender = sender
        self.recipient = recipient
        self.subject = subject
        self.body = body

    def is_valid(self):
        return self.sender and self.recipient and self.body

    def __str__(self):
        return "f='%s' t='%s' s='%s' b='%s'" % (self.sender,
                                               self.recipient,
                                               self.subject,
                                               self.body)

class SMSWall:
    def __init__(self, conf):
        self.msg = None
        self.conf = conf
        self.log = self.conf.log
        self.log.debug("Init done.") 

    def handle_incoming(self, message, confirmed=False):
        self.log.info("Incoming: %s" % message)
        self.msg = message
        if not message.is_valid():
            log.debug("Ignoring invalid message.")
            return
        if message.body.startswith(self.conf.cmd_char):
            try:
                cmd, args = message.body[1:].split(None, 1)
                self.parse_command(message, cmd, args, confirmed)
            except:
                log.debug("Failed to process command: %s" % message)
        elif message.recipient == self.conf.app_number:
            # XXX: should we assert confirmed==False here?
            self.confirm_action(message.body, message.sender)
        else:
            self.send_to_list(message)

    def parse_command(self, message, command, arguments):
        """ Recognize command, parse arguments, and call appropriate handler.
        """
        raise NotImplementedError

    def confirm_action(self, actioncode, sender):
        """ Confirm some previous action. Sensitive actions, like deleting a
        list, may need to be confirmed before they are actually executed. These
        actions are stored in the confirm_action table, which we should
        periodically flush. The stored action is just a command message that
        gets re-submitted to handle_incoming with the 'confirmed' flag set to
        true.

        Actioncodes are short hashes over the action command, sender, and sent time.
        """
        raise NotImplementedError

    def send_to_list(self, message):
        """ Send a message to a list. """
        raise NotImplementedError

    def clean_confirm_actions(self, age):
        """ Remove all confirm_actions older than age. """
        raise NotImplementedError

    def reply(self, body):
        """ Convenience function to respond to the sender of the app's message.
        """
        m = Message(self.conf.app_number, self.msg.sender, None, body)
        self.log.debug("Replying with: %s" % m)


class Config:
    def __init__(self, config_dict, logger):
        self.config_dict = config_dict
        self.log = logger
        self.db = sqlite3.connect(self.db_file)
        self.log.debug("Connected to DB: %s" % self.db_file)

    @property
    def db_file(self):
        return self.config_dict['db_file']

    @property
    def cmd_char(self):
        return self.config_dict['command_char']

    @property
    def app_number(self):
        return self.config_dict['app_number']

    @property
    def min_shortcode(self):
        return self.config_dict['min_shortcode']

    @property
    def max_shortcode(self):
        return self.config_dict['max_shortcode']

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="SMS Mailing Lists for BM.")
    parser.add_argument('--from', '-f', action='store', dest='sender', \
                        help="Sender of incoming message.")
    parser.add_argument('--to', '-t', action='store', dest='recipient', \
                        help="Recipient of incoming message.")
    parser.add_argument('--subject', '-s', action='store', dest='subject', \
                        help="Subject of incoming message.", default="") 
    parser.add_argument('--message', '-m', action='store', dest='message', \
                        help="Body of incoming message.") 
    parser.add_argument('--clean-confirm', action='store', dest='clean', \
                        help="Remove all pending confirm actions older than" +
                             "given age (0 removes everything).", type=int)
    parser.add_argument('--config', '-c', action='store', dest='config', \
                        help="Configuration file (default: smswall.yaml)", \
                        default="smswall.yaml")
    parser.add_argument('--log', '-l', action='store', dest='logfile', \
                        help="Log file (default: smswall.log)", \
                        default="smswall.log")
    parser.add_argument('--debug', action='store_true', dest='debug_mode', \
                        help="Enable debug logging.")
    args = parser.parse_args()

    conf_file = open(args.config, "r")
    config_dict = yaml.load("".join(conf_file.readlines()))

    log = logging.getLogger('smswall')
    if args.debug_mode:
        logging.basicConfig(filename=args.logfile, level=logging.DEBUG)
    else:
        logging.basicConfig(filename=args.logfile)

    conf = Config(config_dict, log)

    msg = Message(args.sender, args.recipient, args.subject, args.message)
    app = SMSWall(conf)

    # Do this before processing any messages so we don't trash any confirm
    # actions the message creates.
    if args.clean:
        app.clean_confirm_actions(args.clean)

    app.handle_incoming(msg)
