from Message import *

class List:
    """ This class is a wrapper around all the list-centric commands. """
    def __init__(self, shortcode, app):
        self.shortcode = shortcode
        self.app = app # the SMSWall app that made this List object
        self.conf = app.conf
        self.db = self.conf.db_conn

    def exists(self):
        cur = self.db.cursor()
        cur.execute("SELECT * FROM %s WHERE shortcode=?" % self.conf.t_list, (self.shortcode,))
        if cur.fetchone():
            return True
        return False

    def is_reserved(self):
        return self.shortcode == self.conf.app_number

    def is_owner(self, number):
        r = self.db.execute("SELECT * FROM %s WHERE list=? AND owner=?" % self.conf.t_owner, (self.shortcode, number))
        if len(r.fetchall()):
            return True
        return False

    def only_owners_can_post(self):
        """ Returns true if the list only allows owners to post, and false
        otherwise. """
        r = self.db.execute("SELECT owner_only FROM %s WHERE shortcode=?" % self.conf.t_list, (self.shortcode,))
        return bool(r.fetchone()[0])

    def is_public(self):
        """ Returns true if the list allows anyone to join, or false if only
        owners can add members. """
        r = self.db.execute("SELECT is_public FROM %s WHERE shortcode=?" % self.conf.t_list, (self.shortcode,))
        return bool(r.fetchone()[0])

    def create(self, initial_owner, owners_only=False, is_public=True):
        if not self.conf.allow_list_creation:
            self.app.reply("List creation is disabled, sorry!")

        if not self.app.is_valid_shortcode(self.shortcode):
            self.app.reply("The shortcode you selected is invalid. Please " \
                           + "choose a number between %d and %d." % \
                           (self.conf.min_shortcode, self.conf.max_shortcode))
        elif self.exists():
            self.app.reply("The shortcode '%s' is already in use." % self.shortcode)
        else:
            self.conf.log.info("Creating list %s" % self.shortcode)
            items = (self.shortcode, owners_only, is_public)
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

            res = db.execute("SELECT member FROM %s WHERE list=?" % self.conf.t_membership, (sc,))
            members = res.fetchall()

            db.execute("BEGIN TRANSACTION")
            db.execute("DELETE FROM %s WHERE shortcode=?" % self.conf.t_list, (sc,))
            db.execute("DELETE FROM %s WHERE list=?" % self.conf.t_membership, (sc,))
            db.execute("DELETE FROM %s WHERE list=?" % self.conf.t_owner, (sc,))
            db.commit()

            for m in members:
                msg = Message(self.conf.app_number, str(m[0]), None, "The list %s has been deleted, and all members (including you!) have been removed." % self.shortcode)
                self.app.send(msg)
            self.app.reply("The list %s has been deleted." % self.shortcode)
        else:
            self.app.add_pending_action(self.app.msg)

    def add_user(self, number):
        """ Add the specified user to the list """
        self.conf.log.info("Adding user '%s' to list '%s'" % (number, self.shortcode))
        if not self.exists():
            self.app.reply("Sorry! The list '%s' doesn't exist!" % self.shortcode)
            return
        db = self.db
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
        # TODO: send "you've been removed"
        db.commit()

    def set_owner_only_posting(self, owners_only):
        """ Set whether or not the list allows non-owners to post. If true,
        then only list owners may post. If false, any member of the list may
        post. Non-members may never post.
        """
        self.conf.log.info("List '%s': Setting owner_only to '%s'" % (self.shortcode, bool(owners_only)))
        db = self.db
        if not self.exists():
            self.app.reply("The list '%s' does not exist." % self.shortcode)
            return
        items = (1 if owners_only else 0, self.shortcode)
        db.execute("UPDATE OR IGNORE %s SET owner_only=? WHERE shortcode=?" % self.conf.t_list, items)
        db.commit()

    def set_list_public(self, is_public):
        self.conf.log.info("List '%s': Setting is_public to '%s'" % (self.shortcode, bool(is_public)))
        db = self.db
        if not self.exists():
            self.app.reply("The list '%s' does not exist." % self.shortcode)
            return
        items = (1 if is_public else 0, self.shortcode)
        db.execute("UPDATE OR IGNORE %s SET is_public=? WHERE shortcode=?" % self.conf.t_list, items)
        db.commit()

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
        db.execute("DELETE FROM %s WHERE list=? AND owner=?" % t_owner, (self.shortcode, number))
        db.commit()

    def post(self, message):
        self.conf.log.info("Posting to list '%s' message: %s" % (self.shortcode, message))
        item = (self.shortcode,)
        r = self.db.execute("SELECT member FROM membership WHERE list=?", item)
        members = [str(m[0]) for m in r.fetchall() if not str(m[0]) == str(message.sender)]
        for m in members:
            msg = Message(self.shortcode, m, message.subject, message.body + " --from: %s" % message.sender)
            self.app.send(msg)
