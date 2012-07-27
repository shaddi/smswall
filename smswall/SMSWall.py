import logging
import sqlite3
import yaml

from smswall import *

class SMSWall:
    def __init__(self, conf):
        self.msg = None
        self.conf = conf
        self.db = conf.db_conn
        self.sender = self._init_sender(self.conf.sender_type)
        self._init_db(self.db)
        self.log = self.conf.log
        self.log.debug("Init done.")

    def _init_sender(self, sender_type):
        """ Returns a Sender object according to the specified sender type.
        Currently, we support one type of Sender:
            - "log": Write the sent SMS messages to a log file
        """
        if sender_type == "log":
            return LogSender
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
        db.execute("CREATE TABLE IF NOT EXISTS %s (shortcode TEXT, owner_only INTEGER, is_public INTEGER)" % self.conf.t_list)
        db.execute("CREATE TABLE IF NOT EXISTS %s (list TEXT, member TEXT)" % self.conf.t_membership)
        db.execute("CREATE TABLE IF NOT EXISTS %s (list TEXT, owner TEXT)" % self.conf.t_owner)
        db.execute("CREATE TABLE IF NOT EXISTS %s (time REAL, sender TEXT, receiver TEXT, command TEXT)" % self.conf.t_confirm)
        db.commit()


    def handle_incoming(self, message, confirmed=False):
        self.log.info("Incoming: %s" % message)
        self.msg = message
        if not message.is_valid():
            log.info("Ignoring invalid message.")
            return
        if message.body.startswith(self.conf.cmd_char):
            try:
                cmd, args = message.body[1:].split(None, 1)
                self.parse_command(message, cmd, args, confirmed)
            except:
                log.debug("Failed to process command: %s" % message)
        elif message.recipient == self.conf.app_number:
            # XXX: should we assert confirmed==False here?
            if "confirm" in message.body:
                self.confirm_action(message.sender)
        else:
            self.send_to_list(message)

    def parse_command(self, message, command, arguments):
        """ Recognize command, parse arguments, and call appropriate handler.
        """
        raise NotImplementedError

    def confirm_action(self, sender):
        """ Confirm some pending action. Sensitive actions, like deleting a
        list, may need to be confirmed before they are actually executed. These
        actions are stored in the confirm_action table, which we should
        periodically flush. The stored action is just a command message that
        gets re-submitted to handle_incoming with the 'confirmed' flag set to
        true. 
        """
        r = self.db.execute("SELECT sender, receiver, command FROM %s WHERE sender=?" % self.conf.t_confirm, sender)
        conf_actions = r.fetchall()
        if len(conf_actions) == 0:
            self.reply("There is nothing awaiting confirmation for you.")
            return

        assert(len(conf_actions) == 1)
        sender, recipient, command = conf_actions[0]
        confirm_msg = Message(sender, recpipient, None, command)
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
        self.sender.send_sms(sender, recv, subj, body)
