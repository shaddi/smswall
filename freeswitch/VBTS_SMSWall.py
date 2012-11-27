#!/usr/bin/python
from libvbts import FreeSwitchMessenger
from freeswitch import *
import logging
import sys
import re
import time
import smswall
import yaml

class FreeSwitchSender(smswall.Sender):

    def __init__(self, smsw):
    	self.smsw = smsw

    def send_sms(self, sender, recipient, subject, data):
        sender = str(sender)
        consoleLog('info', "sending '%s' to %s from %s\n" % (data, recipient, sender)) 
        self.smsw.fs.send_smqueue_sms("", recipient, sender, data)

def chat(message, args):
    args = args.split('|')
    if (len(args) < 3):
        consoleLog('err', 'Missing Args\n')
        exit(1)
    to = args[0]
    fromm = args[1]
    text = args[2]
    if ((not to or to == '') or
        (not fromm or fromm == '')):
        consoleLog('err', 'Malformed Args\n')
        exit(1)

    logging.basicConfig(filename="/var/log/smswall.log", level="DEBUG")
    smswall_log = logging.getLogger("SMSWall.SMSWall")
    conf_file = open("/etc/smswall.yaml", "r")
    config_dict = yaml.load("".join(conf_file.readlines()))
    conf = smswall.Config(config_dict, smswall_log)

    app = smswall.SMSWall(conf)
    app.fs = FreeSwitchMessenger.FreeSwitchMessenger()
    fss = FreeSwitchSender(app)
    app.msg_sender = fss
    consoleLog('info', "Got '%s' from %s to %s\n" % (text, fromm, to))
    msg = smswall.Message(fromm, to, None, text)
    app.handle_incoming(msg)

def fsapi(session, stream, env, args):
    #chat doesn't use message anyhow
    chat(None, args)
