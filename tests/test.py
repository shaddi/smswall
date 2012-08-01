import os
import subprocess
import sys
import commands
import logging
import sqlite3
import timeit

outfile_name = "test.out"
db_file = "smswall.sqlite3"

def query(sql):
    db = sqlite3.connect(db_file, isolation_level=None)
    r = db.execute(sql)
    return len(r.fetchall())

assertions = 0
def test_assert(expr):
    assert(expr)

def clear():
    for f in [db_file, "smswall.log"]:
        try:
            os.remove(f)
        except:
            pass

def get_table_string(table):
    s = "Table '%s'\n" % table
    s += commands.getoutput("sqlite3 %s 'select * from %s;'" % (db_file, table))
    s += "\n"
    return s

def start(description=None):
    outfile = open(outfile_name, "a")
    outfile.write("BEGIN TEST\n")
    if description:
        outfile.write("%s\n" % description)
    outfile.close()


def run(command, db=False, log=False):
    outfile = open(outfile_name, "a")
    outfile.write("RUN: %s\n" % command)
    outfile.close()
    subprocess.check_call(command, shell=True)
    if db:
        report_db()
    if log:
        report_log()

def report_db():
    outfile = open(outfile_name, "a")
    outfile.write("\nTable dump:\n")
    outfile.write(get_table_string("list"))
    outfile.write(get_table_string("membership"))
    outfile.write(get_table_string("owner"))
    outfile.close()

def report_log():
    outfile = open(outfile_name, "a")
    outfile.write("\nLogfile:\n")
    outfile.close()
    os.system("cat smswall.log >> %s" % outfile_name)

def write_to_output(string):
    outfile = open(outfile_name, "a")
    outfile.write("%s\n" % string)
    outfile.close()

"""
Test cases. Every function with the word "testcase" in its name will be
automatically run.
"""
def testcase1():
    clear()
    start("Test 1: Create list, add member, send to list.")
    run("python smswall.py -t 1000 -f 1234 -m 'create 1500'")
    run("python smswall.py -t 1500 -f 1234 -m 'add 43210'")
    run("python smswall.py -t 1500 -f 1234 -m 'test message'")
    assert query("select * from list where shortcode='1500'") == 1
    assert query("select * from membership where list='1500'") == 2

def testcase2():
    clear()
    start("Test 2: Create list, add member, then delete list and confirm deletion.")
    run("python smswall.py -t 1000 -f 1234 -m 'create 1600'")
    run("python smswall.py -t 1600 -f 1234 -m 'add 43210'")
    assert query("select * from list where shortcode='1600'") == 1
    assert query("select * from membership where list='1600'") == 2
    run("python smswall.py -t 1000 -f 1234 -m 'delete 1600'")
    assert query("select * from list where shortcode='1600'") == 1
    assert query("select * from membership where list='1600'") == 2
    assert query("select * from confirm where sender=1234") == 1
    run("python smswall.py -t 1000 -f 1234 -m 'confirm'")
    assert query("select * from list where shortcode='1600'") == 0
    assert query("select * from membership where list='1600'") == 0
    assert query("select * from owner where list='1600'") == 0
    assert query("select * from confirm") == 0
    assert query("select * from confirm where sender=1234") == 0

def testcase3():
    clear()
    start("Test 3: Create invalid list.")
    run("python smswall.py -t 1000 -f 1234 -m 'create 16000'")
    assert query("select * from list where shortcode='1600'") == 0

def testcase4():
    clear()
    start("Test 4: Send 'help' to a non-list, non-app number.")
    run("python smswall.py -t 1251 -f 1234 -m 'help'")

def testcase5():
    clear()
    start("Test 5: Create list, cycle through each of public/private and open/closed. Test join while public/private.")
    run("python smswall.py -t 1000 -f 1234 -m 'create 1600'")
    assert query("select * from list where shortcode=1600 and is_public=1") == 1
    run("python smswall.py -t 1600 -f 54321 -m 'join'")
    assert query("select * from membership where list='1600'") == 2
    run("python smswall.py -t 1600 -f 1234 -m 'makeprivate 1600'")
    assert query("select * from list where shortcode=1600 and is_public=1") == 1
    run("python smswall.py -t 1600 -f 1234 -m 'makeprivate'")
    assert query("select * from list where shortcode=1600 and is_public=0") == 1
    run("python smswall.py -t 1600 -f 43210 -m 'join'")
    assert query("select * from membership where list='1600'") == 2
    run("python smswall.py -t 1600 -f 1234 -m 'makeclosed'")
    assert query("select * from list where shortcode=1600 and owner_only=1") == 1
    run("python smswall.py -t 1600 -f 1234 -m 'makeopen'")
    assert query("select * from list where shortcode=1600 and owner_only=0") == 1

count = 0
def counter(reset=False):
    global count
    count += 1
    return count

def stress_testcase():
    clear()
    #"run(%s)" % ("python smswall.py -t 1000 -f 1234 -m 'create %d'" % (counter() + 3000)
    #'run("python smswall.py -t 1000 -f 1234 -m \'create %(iter)\'")' % {"iter": counter()+3000}
    t = timeit.Timer('run("python smswall.py -t 1000 -f 1234 -m \'create %d\'" % (counter()+3000))', "from __main__ import run, counter")
    r = t.timeit(100) / 100
    write_to_output("List creation: %s sec per list" % (r))


if __name__ == "__main__":
    verbose = False
    if len(sys.argv) > 1:
        if sys.argv[1] == "v":
            verbose = True
    outfile = open(outfile_name, "w")
    outfile.close()

    os.system("tail -f test.out | less")
    global_vars = globals().copy()
    tests = sorted([eval(i) for i in global_vars if "testcase" in i])
    for t in tests:
        try:
            t()
            write_to_output(">>>> PASSED: %s" % t.__name__)
        except AssertionError as e:
            write_to_output(">>>> FAILED: %s" % t.__name__)
            raise
        except:
            write_to_output(">>>> FAILED: %s" % t.__name__)
            report_log()
            raise
        finally:
            if verbose:
                report_db()
                report_log()

