#!/usr/bin/python

import sqlite3

"""
A hacky script to keep a "everyone who ever joined the network" mailing list up
to date. Reads all the numbers from the subscriber registry, loads them
directly into the smswall DB.

This should be set up as a cron job to run every few minutes.
"""

subscriber_dbfile = "/var/lib/asterisk/sqlite3dir/sqlite3.db"
smswall_dbfile = "/etc/OpenBTS/smswall.sqlite3"
everyone_list_shortcode = 9999

smswall_db = sqlite3.connect(smswall_dbfile)
subscriber_db = sqlite3.connect(subscriber_dbfile)

# make sure the "everyone" list exists
r = smswall_db.execute("SELECT * FROM list WHERE shortcode=?", (everyone_list_shortcode,))
if not len(r.fetchall()) == 1:
    exit("The everyone list shortcode doesn't exist.")

# get numbers from subscriber registry
r = subscriber_db.execute("SELECT callerid FROM sip_buddies")
numbers = [str(x[0]) for x in r.fetchall()]

# insert the numbers into the smswall db
for n in numbers:
    r = smswall_db.execute("INSERT INTO membership VALUES(?,?)", (everyone_list_shortcode, n))
smswall_db.commit()

smswall_db.close()
subscriber_db.close()
