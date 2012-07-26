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
