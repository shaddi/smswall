import os
import subprocess
import sys
import commands
import logging
import sqlite3
import timeit

# globals
count = 0
verbose = False
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
    print "BEGIN TEST"
    if description:
        print description


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
    run("python smswall.py -t 1000 -f 12345 -m 'create 1500'")
    run("python smswall.py -t 1500 -f 12345 -m 'add 43210'")
    run("python smswall.py -t 1500 -f 12345 -m 'test message'")
    assert query("select * from list where shortcode='1500'") == 1
    assert query("select * from membership where list='1500'") == 2

def testcase2():
    clear()
    start("Test 2: Create list, add member, then delete list and confirm deletion.")
    run("python smswall.py -t 1000 -f 12345 -m 'create 1600'")
    run("python smswall.py -t 1600 -f 12345 -m 'add 43210'")
    assert query("select * from list where shortcode='1600'") == 1
    assert query("select * from membership where list='1600'") == 2
    run("python smswall.py -t 1000 -f 12345 -m 'delete 1600'")
    assert query("select * from list where shortcode='1600'") == 1
    assert query("select * from membership where list='1600'") == 2
    assert query("select * from confirm where sender=12345") == 1
    run("python smswall.py -t 1000 -f 12345 -m 'confirm'")
    assert query("select * from list where shortcode='1600'") == 0
    assert query("select * from membership where list='1600'") == 0
    assert query("select * from owner where list='1600'") == 0
    assert query("select * from confirm") == 0
    assert query("select * from confirm where sender=12345") == 0

def testcase3():
    clear()
    start("Test 3: Create invalid list.")
    run("python smswall.py -t 1000 -f 12345 -m 'create 16000'")
    assert query("select * from list where shortcode='1600'") == 0

def testcase4():
    clear()
    start("Test 4: Send 'help' to a non-list, non-app number.")
    run("python smswall.py -t 1251 -f 12345 -m 'help'")

def testcase5():
    clear()
    start("Test 5: Create list, cycle through each of public/private and open/closed. Test join while public/private.")
    run("python smswall.py -t 1000 -f 12345 -m 'create 1600'")
    assert query("select * from list where shortcode=1600 and is_public=1") == 1

    run("python smswall.py -t 1600 -f 55555 -m 'join'")
    assert query("select * from membership where list='1600'") == 2

    run("python smswall.py -t 1600 -f 12345 -m 'makeprivate 1600'")
    assert query("select * from list where shortcode=1600 and is_public=1") == 1
    assert log_has_string("Invalid command")

    run("python smswall.py -t 1600 -f 12345 -m 'makeprivate'")
    assert query("select * from list where shortcode=1600 and is_public=0") == 1

    run("python smswall.py -t 1600 -f 43210 -m 'join'")
    assert query("select * from membership where list='1600'") == 2

    run("python smswall.py -t 1600 -f 12345 -m 'makeclosed'")
    assert query("select * from list where shortcode=1600 and owner_only=1") == 1

    run("python smswall.py -t 1600 -f 55555 -m 'testmessage'")
    assert log_has_string("[0, 1000, '55555', None, 'Sorry, only list owners may post to this list.']")

    run("python smswall.py -t 1600 -f 12345 -m 'addowner 55555'")
    assert query("select * from owner where list=1600") == 2

    run("python smswall.py -t 1600 -f 55555 -m 'testmessage'")
    assert log_has_string("[1, '55555', '55555', '', 'testmessage']")
    assert not log_has_string("[2, '55555', '55555', '', 'testmessage']")

    run("python smswall.py -t 1600 -f 12345 -m 'makeopen'")
    assert query("select * from list where shortcode=1600 and owner_only=0") == 1

def testcase6():
    clear()
    start("Test 6: Test clearing pending actions (create list, then delete, then clear confirm).")
    run("python smswall.py -t 1000 -f 12345 -m 'create 1600'")
    assert query("select * from list where shortcode='1600'") == 1
    assert query("select * from membership where list='1600'") == 1
    assert query("select * from confirm where sender=12345") == 0
    run("python smswall.py -t 1000 -f 12345 -m 'delete 1600'")
    assert query("select * from list where shortcode='1600'") == 1
    assert query("select * from membership where list='1600'") == 1
    assert query("select * from confirm where sender=12345") == 1
    run("python smswall.py --clean-confirm 0")
    assert query("select * from list where shortcode='1600'") == 1
    assert query("select * from membership where list='1600'") == 1
    assert query("select * from confirm where sender=12345") == 0

"""
Performance tests.
"""
def perf1_testcase():
    clear()
    num = 100
    start("Perf test 1: Create %d lists." % num)
    t = timeit.Timer('run("python smswall.py -t 1000 -f 1234 -m \'create %d\'" % (counter()+3000))', "from __main__ import run, counter")
    r = t.timeit(num) / num
    print "List creation: %s sec per list" % (r)
    assert r < 1 # TODO: pitiful time, need to improve

def perf2_testcase():
    clear()
    num = 1000
    start("Perf test 2: Create 1 list, handle %d joins." % num)
    run("python smswall.py -t 1000 -f 1234 -m 'create 1500'")
    t = timeit.Timer('run("python smswall.py -t 1500 -f %d -m \'join\'" % (counter()+10000))', "from __main__ import run, counter")
    r = t.timeit(num) / num
    print "Join: %s sec per list join" % (r)

def perf3_testcase():
    clear()
    num = 100
    start("Perf test 3: Create 1 list, %d users. Handle %d posts." % (num, num))
    run("python smswall.py -t 1000 -f 1234 -m 'create 1500'")
    t = timeit.Timer('run("python smswall.py -t 1500 -f %d -m \'join\'" % (counter()+10000))', "from __main__ import run, counter")
    r = t.timeit(num) / num
    print "Join: %s sec per list join" % (r)
    t = timeit.Timer('run("python smswall.py -t 1500 -f 1234 -m testmessage")', "from __main__ import run")
    r = t.timeit(num) / num
    print "Post: %s sec per post (sent to %d users, %.5f per user)" % (r, num, r/num)

def perf4_testcase():
    clear()
    num = 1000
    start("Perf test 3: Create 1 list, %d users. Handle %d posts." % (num, num))
    run("python smswall.py -t 1000 -f 1234 -m 'create 1500'")
    t = timeit.Timer('run("python smswall.py -t 1500 -f %d -m \'join\'" % (counter()+10000))', "from __main__ import run, counter")
    r = t.timeit(num) / num
    print "Join: %s sec per list join" % (r)
    t = timeit.Timer('run("python smswall.py -t 1500 -f 1234 -m testmessage")', "from __main__ import run")
    r = t.timeit(num) / num
    print "Post: %s sec per post (sent to %d users, %.5f per user)" % (r, num, r/num)

if __name__ == "__main__":
    global verbose
    if len(sys.argv) > 1:
        if sys.argv[1] == "v":
            verbose = True

    global_vars = globals().copy()
    tests = sorted([eval(i) for i in global_vars if ("testcase" in i)])
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

