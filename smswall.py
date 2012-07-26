#!/usr/bin/python 
import argparse
import logging
import yaml

import smswall

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
                    help="Remove all pending confirm actions older than " +
                         "given age (0 removes everything).", type=int)
parser.add_argument('--config', '-c', action='store', dest='config', \
                    help="Configuration file (default: /etc/smswall.yaml)", \
                    default="/etc/smswall.yaml")
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

conf = smswall.Config(config_dict, log)
msg = smswall.Message(args.sender, args.recipient, args.subject, args.message)
app = smswall.SMSWall(conf)

# Do this before processing any messages so we don't trash any confirm
# actions the message creates.
if args.clean is not None:
    app.clean_confirm_actions(args.clean)

# No point in handling an empty message, do this to keep logs cleaner.
if not msg.is_empty():
    app.handle_incoming(msg)

app.db.close()
