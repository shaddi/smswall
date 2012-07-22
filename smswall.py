import logging
import sqlite3
import yaml

class List:
    """ This class is a wrapper around all the list-centric commands. """
    def __init__(self, shortcode, app):
        self.shortcode = shortcode
        self.app = app # the SMSWall app that made this List object
        self.conf = app.conf
        self.db = self.conf.db_conn

    def exists(self):
        cur = self.db.cursor()
        cur.execute("SELECT * FROM %s WHERE shortcode=?" % self.conf.t_list, self.shortcode)
        if cur.rowcount:
            return True
        return False

    def is_owner(self, number):
        r = self.db.execute("SELECT * FROM %s WHERE list=? AND owner=?" % self.conf.t_owner, (self.shortcode, number))
        if r.rowcount:
            return True
        return False

    def allows_public_posts(self):
        """ Returns true if the list allows public posts or false otherwise. If
        false, only owners are allowed to post. """
        r = self.db.execute("SELECT allows_public FROM %s WHERE list=?" % self.conf.t_list, (self.shortcode,))
        allows_public = bool(r.fetchone()[0])
        return allows_public

    def is_open(self):
        """ Returns true if the list allows anyone to join, or false if only
        owners can add members. """
        r = self.db.execute("SELECT is_open FROM %s WHERE list=?" % self.conf.t_list, (self.shortcode,))
        is_open = bool(r.fetchone()[0])
        return is_open

    def create(self, initial_owner, allows_public=True, is_open=True):
        if not self.app.is_valid_shortcode(self.shortcode):
            self.app.reply("The shortcode you selected is invalid. Please " \
                           + "choose a number between %d and %d." % \
                           (self.conf.min_shortcode, self.conf.max_shortcode))
        elif self.exists():
            self.app.reply("The shortcode '%s' is already in use." % self.shortcode)
        else:
            self.conf.log.info("Creating list %s" % self.shortcode)
            items = (self.shortcode, allows_public, is_open)
            self.db.execute("INSERT INTO %s VALUES (?,?,?)" % self.conf.t_list, items)
            self.make_owner(initial_owner)

    def delete(self, confirmed=False):
        """ If confirmed, remove list from list table, then all associated
        members. Otherwise, save message in confirm_action table.
        """
        if confirmed:
            self.conf.log.info("Deleting list %s" % self.shortcode)
            db = self.db
            sc = self.shortcode

            res = execute("SELECT member FROM %s WHERE list=?" % self.conf.t_membership, (sc,))
            members = res.fetchall()

            db.execute("BEGIN TRANSACTION")
            db.execute("DELETE FROM %s WHERE shortcode=?" % self.conf.t_list, (sc,))
            db.execute("DELETE FROM %s WHERE list=?" % self.conf.t_membership, (sc,))
            db.execute("DELETE FROM %s WHERE list=?" % self.conf.t_owner, (sc,))
            db.commit()

            for m in members:
                msg = Message(self.conf.app_number, m, None, \
                              "The list %s has been deleted, and all members" +
                              " (including you!) have been removed." \
                              % self.shortcode)
                self.app.send(msg)
            self.app.reply("The list %s has been deleted." % self.shortcode)
        else:
            self.app.add_pending_action(self.app.msg)

    def add_user(self, number):
        """ Add the specified user to the list """
        self.conf.log.info("Adding user '%s' to list '%s'" % (number, self.shortcode))
        item = (self.shortcode, number)
        db.execute("INSERT OR IGNORE INTO %s(list, member) VALUES (?,?)" % self.conf.t_membership, item)
        db.commit()
        # TODO: only send message if insert actually touched something
        msg = Message(self.conf.app_number, number, None, "You've been added to the list '%s'." % self.shortcode)
        self.app.send(msg)

    def delete_user(self, number):
        """ Delete the specified user from the list """
        self.conf.log.info("Deleting user '%s' from list '%s'" % (number, self.shortcode))
        db = self.db
        db.execute("DELETE FROM %s WHERE member=?" % self.conf.t_membership, (number,))
        db.execute("DELETE FROM %s WHERE list=? AND owner=?" % self.conf.t_owner, (self.shortcode, number))
        db.commit()

    def enable_public_posts(self):
        raise NotImplementedError

    def disable_public_posts(self):
        raise NotImplementedError

    def make_list_open(self):
        raise NotImplementedError

    def make_list_closed(self):
        raise NotImplementedError

    def make_owner(self, number):
        self.add_user(number)
        self.conf.log.info("Making user '%s' owner of list '%s'" % (number, self.shortcode))
        db = self.db
        t_owner = self.conf.t_owner
        db.execute("INSERT OR IGNORE INTO %s(list, owner) VALUES (?,?)" % t_owner, (self.shortcode, number))
        db.commit()

    def unmake_owner(self, number):
        self.conf.log.info("Removing user '%s' as owner of list '%s'" % (number, self.shortcode))
        db = self.db
        t_owner = self.conf.t_owner
        db.execute("DELETE FROM %s WHERE list=?" % t_owner, (self.shortcode, number))
        db.commit()

    def post(self, message):
        self.conf.log.info("Posting to list '%s' message: %s" % self.shortcode, message)
        item = (self.shortcode,)
        r = self.db.execute("SELECT member FROM membership WHERE list=?", item)
        members = r.fetchall()
        for m in members:
            msg = Message(message.sender, m, message.subject, message.body)
            self.app.send(msg)


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
        self.db = conf.db_conn
        self._init_db(self.db)
        self.log = self.conf.log
        self.log.debug("Init done.") 

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
        db.execute("CREATE TABLE IF NOT EXISTS %s (shortcode TEXT, allows_public INTEGER, is_open INTEGER)" % self.conf.t_list)
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
        raise NotImplementedError

class Config:
    def __init__(self, config_dict, logger):
        self.config_dict = config_dict
        self.log = logger

        # verify safety of db table names
        self._scrub(self.config_dict['t_list'])
        self._scrub(self.config_dict['t_membership'])
        self._scrub(self.config_dict['t_owner'])
        self._scrub(self.config_dict['t_confirm'])

        self.db_conn = sqlite3.connect(self.db_file)
        self.log.debug("Connected to DB: %s" % self.db_file)

    def _scrub(self, string):
        """ Make sure the string is alphanumeric. We do this to sanitize our
        table names (since DB-API parameter substitution doesn't work for table
        names). """
        if not string.isalnum():
            raise ValueError("Table name cannot include non-alphanumerics.")
        return string

    @property
    def t_list(self):
        return self._scrub(self.config_dict['t_list'])

    @property
    def t_membership(self):
        return self._scrub(self.config_dict['t_membership'])

    @property
    def t_owner(self):
        return self._scrub(self.config_dict['t_owner'])

    @property
    def t_confirm(self):
        return self._scrub(self.config_dict['t_confirm'])

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
    if args.clean is not None:
        app.clean_confirm_actions(args.clean)

    app.handle_incoming(msg)
    app.db.close()
