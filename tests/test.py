import argparse
import os
import subprocess
import sys
import commands
import logging
import random
import sqlite3
import timeit

"""
Hacky hacky hacky testing for smswall. Make sure your config is set to use the
'test' sender type or this will fail! To run stress tests, you need to modify
the appropriate parameter in __main__.
"""

# globals
count = 0
db_file = "smswall.sqlite3"

def query(sql):
    db = sqlite3.connect(db_file, isolation_level=None)
    r = db.execute(sql)
    return len(r.fetchall())

assertions = 0
def test_assert(expr):
    assert(expr)

def clear():
    global count
    for f in [db_file, "smswall.log"]:
        try:
            os.remove(f)
        except:
            pass
    count = 0

def get_table_string(table):
    s = "Table '%s'\n" % table
    s += commands.getoutput("sqlite3 %s 'select * from %s;'" % (db_file, table))
    s += "\n"
    return s

def start(description=None):
    global quiet
    if not quiet:
        if description:
            print "BEGIN TEST --> %s" % description
        else:
            print "BEGIN TEST"


def run(command, db=False, log=False):
    if verbose:
        print "RUN: %s" % command
    subprocess.check_call(command, shell=True)
    if db:
        report_db()
    if log:
        report_log()

def report_db():
    print "Table dump:"
    print get_table_string("list")
    print get_table_string("membership")
    print get_table_string("owner")

def report_log():
    print "Logfile:"
    logfile = open("smswall.log", "r")
    for line in logfile:
        print line,
    logfile.close()

def log_has_string(string):
    r = False
    logfile = open("smswall.log", "r")
    for line in logfile:
        if "testsender" in line:
            if string in line:
                r = True
    logfile.close()
    return r

def counter(reset=False):
    global count
    count += 1
    return count

"""
Test cases. Every function with the word "testcase" in its name will be
automatically run.
"""
def testcase1():
    clear()
    start("Test 1: Create list, add member, send to list.")
    run("python smswall-interactive -t 1000 -f 12345 -m 'create 1500'")
    run("python smswall-interactive -t 1500 -f 12345 -m 'add 43210'")
    run("python smswall-interactive -t 1500 -f 12345 -m 'test message'")
    assert query("select * from list where shortcode='1500'") == 1
    assert query("select * from membership where list='1500'") == 2

def testcase2():
    clear()
    start("Test 2: Create list, add member, then delete list and confirm deletion.")
    run("python smswall-interactive -t 1000 -f 12345 -m 'create 1600'")
    run("python smswall-interactive -t 1600 -f 12345 -m 'add 43210'")
    assert query("select * from list where shortcode='1600'") == 1
    assert query("select * from membership where list='1600'") == 2
    run("python smswall-interactive -t 1000 -f 12345 -m 'delete 1600'")
    assert query("select * from list where shortcode='1600'") == 1
    assert query("select * from membership where list='1600'") == 2
    assert query("select * from confirm where sender=12345") == 1
    run("python smswall-interactive -t 1000 -f 12345 -m 'confirm'")
    assert query("select * from list where shortcode='1600'") == 0
    assert query("select * from membership where list='1600'") == 0
    assert query("select * from owner where list='1600'") == 0
    assert query("select * from confirm") == 0
    assert query("select * from confirm where sender=12345") == 0

def testcase3():
    clear()
    start("Test 3: Create invalid list.")
    run("python smswall-interactive -t 1000 -f 12345 -m 'create 16000'")
    assert query("select * from list where shortcode='1600'") == 0

def testcase4():
    clear()
    start("Test 4: Send 'help' to a non-list, non-app number.")
    run("python smswall-interactive -t 1251 -f 12345 -m 'help'")

def testcase5():
    clear()
    start("Test 5: Create list, cycle through each of public/private and open/closed. Test join while public/private.")
    run("python smswall-interactive -t 1000 -f 12345 -m 'create 1600'")
    assert query("select * from list where shortcode=1600 and is_public=1") == 1

    run("python smswall-interactive -t 1600 -f 55555 -m 'join'")
    assert query("select * from membership where list='1600'") == 2

    run("python smswall-interactive --debug -t 1600 -f 12345 -m 'makeprivate 1600'")
    assert query("select * from list where shortcode=1600 and is_public=1") == 1
    assert log_has_string("Invalid command")

    run("python smswall-interactive -t 1600 -f 12345 -m 'makeprivate'")
    assert query("select * from list where shortcode=1600 and is_public=0") == 1

    run("python smswall-interactive -t 1600 -f 43210 -m 'join'")
    assert query("select * from membership where list='1600'") == 2

    run("python smswall-interactive -t 1600 -f 12345 -m 'makeclosed'")
    assert query("select * from list where shortcode=1600 and owner_only=1") == 1

    run("python smswall-interactive --debug -t 1600 -f 55555 -m 'testmessage'")
    assert log_has_string("[0, 1000, '55555', None, 'Sorry, only list owners may post to this list.']")

    run("python smswall-interactive -t 1600 -f 12345 -m 'addowner 55555'")
    assert query("select * from owner where list=1600") == 2

    run("python smswall-interactive --debug -t 1600 -f 55555 -m 'testmessage'")
    assert log_has_string("[0, '1600', '12345', '', '(from: 55555) testmessage']")
    assert not log_has_string("[1, '1600', '55555', '', '(from: 55555) testmessage']")

    run("python smswall-interactive -t 1600 -f 12345 -m 'makeopen'")
    assert query("select * from list where shortcode=1600 and owner_only=0") == 1

def testcase6():
    clear()
    start("Test 6: Test clearing pending actions (create list, then delete, then clear confirm).")
    run("python smswall-interactive -t 1000 -f 12345 -m 'create 1600'")
    assert query("select * from list where shortcode='1600'") == 1
    assert query("select * from membership where list='1600'") == 1
    assert query("select * from confirm where sender=12345") == 0
    run("python smswall-interactive -t 1000 -f 12345 -m 'delete 1600'")
    assert query("select * from list where shortcode='1600'") == 1
    assert query("select * from membership where list='1600'") == 1
    assert query("select * from confirm where sender=12345") == 1
    run("python smswall-interactive --clean-confirm 0")
    assert query("select * from list where shortcode='1600'") == 1
    assert query("select * from membership where list='1600'") == 1
    assert query("select * from confirm where sender=12345") == 0

def testcase7():
    clear()
    start("Test 7: Test removing a user from a list.")
    run("python smswall-interactive -t 1000 -f 12345 -m 'create 1600'")
    run("python smswall-interactive -t 1600 -f 55555 -m 'join'")
    assert query("select * from membership where list='1600'") == 2
    run("python smswall-interactive -t 1600 -f 55555 -m 'remove 55555'")
    assert query("select * from membership where list='1600'") == 2
    run("python smswall-interactive -t 1600 -f 12345 -m 'remove 55555'")
    assert query("select * from membership where list='1600'") == 1

def testcase8():
    clear()
    start("Test 8: Test making a user an owner then removing them.")
    # make the list
    run("python smswall-interactive -t 1000 -f 12345 -m 'create 1600'")
    assert query("select * from membership where list='1600'") == 1
    assert query("select * from owner where list='1600'") == 1
    # add an owner
    run("python smswall-interactive -t 1600 -f 12345 -m 'addowner 55555'")
    assert query("select * from membership where list='1600'") == 2
    assert query("select * from owner where list='1600'") == 2
    # make sure the new owner can do owner-y things
    run("python smswall-interactive -t 1600 -f 55555 -m 'makeclosed'")
    assert query("select * from list where shortcode=1600 and owner_only=1") == 1
    # revoke their ownership
    run("python smswall-interactive -t 1600 -f 12345 -m 'removeowner 55555'")
    assert query("select * from membership where list='1600'") == 2
    assert query("select * from owner where list='1600'") == 1
    # ensure the old owner can't do owner-y things
    run("python smswall-interactive -t 1600 -f 55555 -m 'makeopen'")
    assert query("select * from list where shortcode=1600 and owner_only=1") == 1

def testcase9():
    clear()
    start("Test 9: Make a user join then leave a list.")
    # make the list
    run("python smswall-interactive -t 1000 -f 12345 -m 'create 1600'")
    assert query("select * from membership where list='1600'") == 1
    assert query("select * from owner where list='1600'") == 1

    run("python smswall-interactive -t 1600 -f 55555 -m 'join'")
    assert query("select * from membership where list='1600'") == 2

    run("python smswall-interactive -t 1600 -f 55555 -m 'leave'")
    assert query("select * from membership where list='1600'") == 1

def testcase10():
    clear()
    start("Test 10: Test handling uppercase commands")
    run("python smswall-interactive -t 1000 -f 12345 -m 'CREATE 1500'")
    run("python smswall-interactive -t 1500 -f 12345 -m 'Add 43210'")
    run("python smswall-interactive -t 1500 -f 12345 -m 'Test Message'")
    assert query("select * from list where shortcode='1500'") == 1
    assert query("select * from membership where list='1500'") == 2

def testcase11():
    clear()
    start("Test 11: Test sending to a non-existent list that user is not a member of.")
    run("python smswall-interactive -t 1500 -f 12345 -m 'Test Message'") # just shouldn't fail

def testcase12():
    clear()
    start("Test 12: Test setting and changing username.")
    run("python smswall-interactive --debug --from 11111 --to 1000 --message 'create 2000'")
    assert log_has_string("Your name has been set to '11111'")
    run("python smswall-interactive --debug --from 12345 --to 2000 --message 'join'")
    assert log_has_string("Your name has been set to '12345'")
    run("python smswall-interactive --debug --from 12345 --to 1000 --message 'setname foo'")
    assert log_has_string("Your name has been set to 'foo'")
    run("python smswall-interactive --debug --from 12345 --to 2000 --message 'test message'")
    assert log_has_string("(from: foo)")

"""
Performance tests.
"""
def perf1_testcase():
    clear()
    num = 100
    start("Perf test 1: Create %d lists." % num)
    t = timeit.Timer('run("python smswall-interactive -t 1000 -f 1234 -m \'create %d\'" % (counter()+3000))', "from __main__ import run, counter")
    r = t.timeit(num) / num
    print "List creation: %s sec per list" % (r)
    assert r < 1 # TODO: pitiful time, need to improve

def perf2_testcase():
    clear()
    num = 1000
    start("Perf test 2: Create 1 list, handle %d joins." % num)
    run("python smswall-interactive -t 1000 -f 1234 -m 'create 1500'")
    t = timeit.Timer('run("python smswall-interactive -t 1500 -f %d -m \'join\'" % (counter()+10000))', "from __main__ import run, counter")
    r = t.timeit(num) / num
    print "Join: %s sec per list join" % (r)

def perf3_testcase():
    clear()
    num = 100
    start("Perf test 3: Create 1 list, %d users. Handle %d posts." % (num, num))
    run("python smswall-interactive -t 1000 -f 1234 -m 'create 1500'")
    t = timeit.Timer('run("python smswall-interactive -t 1500 -f %d -m \'join\'" % (counter()+10000))', "from __main__ import run, counter")
    r = t.timeit(num) / num
    print "Join: %s sec per list join" % (r)
    t = timeit.Timer('run("python smswall-interactive -t 1500 -f 1234 -m testmessage")', "from __main__ import run")
    r = t.timeit(num) / num
    print "Post: %s sec per post (sent to %d users, %.5f per user)" % (r, num, r/num)

def perf4_testcase():
    clear()
    num = 1000
    start("Perf test 3: Create 1 list, %d users. Handle %d posts." % (num, num))
    run("python smswall-interactive -t 1000 -f 1234 -m 'create 1500'")
    t = timeit.Timer('run("python smswall-interactive -t 1500 -f %d -m \'join\'" % (counter()+10000))', "from __main__ import run, counter")
    r = t.timeit(num) / num
    print "Join: %s sec per list join" % (r)
    t = timeit.Timer('run("python smswall-interactive -t 1500 -f 1234 -m testmessage")', "from __main__ import run")
    r = t.timeit(100) / 100
    print "Post: %s sec per post (sent to %d users, %.6f per user)" % (r, num, r/num)

def perf5_testcase():
    clear()
    num = 100
    start("Perf test 5: Create %d lists, 3 users on each, post to every list." % (num))
    for i in xrange(1, num+1):
        run("python smswall-interactive -t 1000 -f 12345 -m 'create %d'" % (i+3000))
        for j in xrange(0,2):
            run("python smswall-interactive -t %d -f %d -m 'join'" % (i+3000, j + random.randint(100000,200000)))
    t = timeit.Timer('run("python smswall-interactive -t %d -f 12345 -m testmessage" % (counter()+3000))', "from __main__ import run, counter")
    r = t.timeit(num) / num
    print "Post: %s sec per post (sent to 3 users, %.5f per user)" % (r, r/3)

def perf6_testcase():
    clear()
    num = 1000
    start("Perf test 6: Create %d lists, 3 users on each, post to every list." % (num))
    for i in xrange(1, num+1):
        run("python smswall-interactive -t 1000 -f 12345 -m 'create %d'" % (i+3000))
        for j in xrange(0,2):
            run("python smswall-interactive -t %d -f %d -m 'join'" % (i+3000, j + random.randint(100000,200000)))
    t = timeit.Timer('run("python smswall-interactive -t %d -f 12345 -m testmessage" % (counter()+3000))', "from __main__ import run, counter")
    r = t.timeit(num) / num
    print "Post: %s sec per post (sent to 3 users, %.5f per user)" % (r, r/3)

"""
Stress tests -- off by default; if we pass these we pass Burning Man.
"""
def stress1_testcase():
    clear()
    num = 100000
    start("Stress test 1: Create 1 list, %d users. Handle %d posts." % (num, num))
    run("python smswall-interactive -t 1000 -f 1234 -m 'create 1500'")
    print "Adding users... "
    db = sqlite3.connect(db_file)
    for i in xrange(100000, 200000):
        db.execute("insert into membership(list, member) values (?,?)", (1500, i))
    db.commit()
    print "Users added."
    t = timeit.Timer('run("python smswall-interactive -t 1500 -f 1234 -m testmessage")', "from __main__ import run")
    r = t.timeit(100) / 100
    print "Post: %s sec per post (sent to %d users, %.6f per user)" % (r, num, r/num)

def stress2_testcase():
    clear()
    num = 7500
    num_users = 500
    start("Stress test 2: Create %d lists, %d users on each, post to every list, in parallel." % (num, num_users))
    print "Setting up... (this may take a few minutes, adding >%d records to the DB!)" % (num*num_users)
    run("python smswall-interactive -t 1000 -f 1234 -m 'create 9998'") # just to initialize things, we never use this
    db = sqlite3.connect(db_file)
    for i in xrange(1, num+1):
        if i % 1000 == 0:
            print "Creating %dth list." % i
        db.execute("insert into list values(?, ?, ?)", (i+2000, False, True))
        db.execute("insert into owner(list, owner) values(?, 12345)", (i+2000,))
        db.execute("insert into membership(list, member) values(?, 12345)", (i+2000,))
        for j in xrange(0,num_users-1): # owner is a member!
            db.execute("insert into membership(list, member) values(?, ?)", (i+2000, random.randint(100000,200000)))
    db.commit()
    print "Setup done."
    t = timeit.Timer('run("python smswall-interactive -t %d -f 12345 -m testmessage &" % (counter()+2000))', "from __main__ import run, counter")
    r = t.timeit(num) / num
    print "Post: %s sec per post (sent to %d users, %.5f per user)" % (r, num_users, r/num_users)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tester for smswall. By default, only runs basic tests.")
    parser.add_argument("-b", action="store_true", dest='basic', help="Run basic tests (default: true).")
    parser.add_argument("-p", action="store_true", dest='perf', help="Run performance tests (default: false).")
    parser.add_argument("-s", action="store_true", dest='stress', help="Run stress tests (default: false).")
    parser.add_argument("-v", action="store_true", dest='verbose', help="Be verbose (default: false).")
    parser.add_argument("-q", action="store_true", dest='quiet', help="Be quiet (only show test results; default: false).")
    args = parser.parse_args()

    global verbose
    verbose = args.verbose

    global quiet
    quiet = args.quiet

    basic = True
    perf = False
    stress = False

    if args.perf:
        perf = True
        basic = args.basic
    if args.stress:
        stress = True
        basic = args.basic

    tests = []
    global_vars = globals().copy()
    if basic:
        tests += sorted([eval(i) for i in global_vars if ("testcase" in i and not "stress" in i and not "perf" in i)])
    if perf:
        tests += sorted([eval(i) for i in global_vars if ("testcase" in i and "perf" in i)])
    if stress:
        tests += sorted([eval(i) for i in global_vars if ("testcase" in i and "stress" in i)])
        print "WARNING: Running stress tests. This will take a while!"
    for t in tests:
        try:
            t()
            print ">>>> PASSED: %s" % t.__name__
        except AssertionError as e:
            print ">>>> FAILED: %s" % t.__name__
            raise
        except:
            print ">>>> FAILED: %s" % t.__name__
            report_log()
            raise
        finally:
            if verbose:
                report_db()
                report_log()

