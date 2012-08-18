import logging
import sqlite3
import time
import yaml

from smswall import *

class SMSWall:
    def __init__(self, conf):
        self.msg = None
        self.conf = conf
        self.db = conf.db_conn
        self.cmd_handler = CommandHandler(self)
        self.msg_sender = self._init_sender(self.conf.sender_type)
        self._init_db(self.db)
        self.log = self.conf.log
        self.log.debug("Init done.")

    def _init_sender(self, sender_type):
        """ Returns a Sender object according to the specified sender type.
        Currently, we support two types of Sender:
            - "log": Write the sent SMS messages to a log file
            - "test": Write the sent SMS messages to an easy-to-parse log
        """
        if sender_type == "log":
            return LogSender()
        if sender_type == "test":
            return TestSender()
        raise ValueError("No sender of type '%s' exists." % sender_type)

    def _init_db(self, db_conn, purge=False):
        # XXX: Should use a separate connection for IMMEDIATE transactions?
        db = db_conn
        if purge:
            db.execute("BEGIN TRANSACTION")
            tables = [self.conf.t_list, self.conf.t_membership, \
                      self.conf.t_owner, self.conf.t_confirm]
            for t in tables:
                db.execute("DROP TABLE %s" % t)
            db.commit()

        # Parameter substitution doesn't work for table names, but we scrub
        # unsafe names in the accessors for the table name properties so these
        # should be fine.
        db.execute("CREATE TABLE IF NOT EXISTS %s (shortcode TEXT PRIMARY KEY, owner_only INTEGER, is_public INTEGER)" % self.conf.t_list)
        db.execute("CREATE TABLE IF NOT EXISTS %s (list TEXT, member TEXT, UNIQUE(list, member) ON CONFLICT IGNORE)" % self.conf.t_membership)
        db.execute("CREATE TABLE IF NOT EXISTS %s (list TEXT, owner TEXT, UNIQUE(list, owner) ON CONFLICT IGNORE)" % self.conf.t_owner)
        db.execute("CREATE TABLE IF NOT EXISTS %s (time REAL, sender TEXT, receiver TEXT, command TEXT)" % self.conf.t_confirm)
        db.commit()

    def is_valid_shortcode(self, number):
        try:
            sc = int(number)
        except ValueError:
            return False

        if sc >= self.conf.min_shortcode and sc <= self.conf.max_shortcode:
            return True

        return False


    def handle_incoming(self, message, confirmed=False):
        self.log.info("Incoming: %s" % message)
        self.msg = message
        if not message.is_valid():
            log.info("Ignoring invalid message.")
            return
        elif self.cmd_handler.looks_like_command(message):
            self.parse_command(message, confirmed)
        else:
            self.post_to_list(message)

    def confirm_action(self, sender):
        """ Confirm some pending action. Sensitive actions, like deleting a
        list, may need to be confirmed before they are actually executed. These
        actions are stored in the confirm_action table, which we should
        periodically flush. The stored action is just a command message that
        gets re-submitted to handle_incoming with the 'confirmed' flag set to
        true.
        """
        db = self.db
        r = db.execute("SELECT sender, receiver, command FROM %s WHERE sender=?" % self.conf.t_confirm, (sender,))
        conf_actions = r.fetchall()
        if len(conf_actions) == 0:
            self.reply("There is nothing awaiting confirmation for you.")
            return

        assert(len(conf_actions) == 1)
        sender, recipient, command = conf_actions[0]
        confirm_msg = Message(sender, recipient, None, command)
        i = (sender,)
        db.execute("DELETE FROM %s WHERE sender=?" % self.conf.t_confirm, i)
        self.handle_incoming(confirm_msg, True)

    def add_pending_action(self, message):
        """ A user can have up to one pending action. This method generates a
        confirmation response to the sender. """
        t_confirm = self.conf.t_confirm
        items = (time.time(), message.sender, message.recipient, message.body)
        self.db.execute("INSERT INTO %s VALUES (?,?,?,?)" % t_confirm, items)
        self.db.commit()
        self.reply("Reply to this message with the word \"confirm\" to " +
                    "confirm your previous command.")

    def post_to_list(self, message):
        """ Post a message to a list. """
        list_ = List(message.recipient, self)
        if not list_.exists():
            self.reply("The list %s doesn't exist." % message.recipient)
            return
        if list_.only_owners_can_post() and not list_.is_owner(message.sender):
            self.reply("Sorry, only list owners may post to this list.")
            return
        list_.post(message)

    def clean_confirm_actions(self, age):
        """ Remove all confirm_actions older than age in minutes. """
        assert(age >= 0)
        db = self.db
        if age == 0:
            self.log.debug("Clearing all confirm actions.")
            db.execute("DELETE FROM %s" % self.conf.t_confirm)
        else:
            age_limit = time.time() - (age * 60)
            self.log.debug("Clearing confirm actions older than %d min." % age)
            db.execute("DELETE FROM %s WHERE time <= ?" % self.conf.t_confirm, (age_limit,))
        db.commit()


    def reply(self, body):
        """ Convenience function to respond to the sender of the app's message.
        """
        m = Message(self.conf.app_number, self.msg.sender, None, body)
        self.log.debug("Replying with: %s" % m)
        self.send(m)

    def send(self, message):
        """ Send the specified message. """
        sender = message.sender
        recv = message.recipient
        subj = message.subject
        body = message.body

        # TODO: do something sensible with return value
        self.msg_sender.send_sms(sender, recv, subj, body)

    def parse_command(self, message, confirmed):
        """ Recognize command, parse arguments, and call appropriate handler.
        """
        if message.body.startswith(self.conf.cmd_char):
            body = message.body[1:]
        else:
            body = message.body

        if len(body.split()) > 1:
            cmd, args = message.body.split(None, 1)
            args = args.split()
        elif len(body.split()) == 1:
            cmd = message.body.split()[0]
            args = None
        else:
            cmd = None
            args = None

        try:
            self.cmd_handler.dispatch(message, cmd, args, confirmed)
        except CommandError as e:
            self.reply(str(e)) # Send the failure message to the user.
