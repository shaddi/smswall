#!/usr/bin/python
from libyate import Yate
from libvbts import YateMessenger
import logging
import sys
import re
import time
import smswall
import yaml

class YateSender(smswall.Sender):

	def __init__(self, smsw):
		self.smsw = smsw

	def send_sms(self, sender, recipient, subject, data):
		sender = str(sender)
		#sender_name = self.smsw.ym.SR_get("name", ("callerid", sender))
		#ipaddr = self.smsw.ym.SR_get("ipaddr", ("callerid", sender))
		#port = str(self.smsw.ym.SR_get("port", ("callerid", sender)))
		self.smsw.ym.send_smqueue_sms(self.smsw.app, recipient, "%s <sip:%s@127.0.0.1>" % (sender, sender), data)

class SMSWall:
	""" initialize the object """
	def __init__(self, to_be_handled):
		self.app = Yate()
		self.app.__Yatecall__ = self.yatecall
		self.log = logging.getLogger("SMSWall.SMSWall")
   		logging.basicConfig(filename="/var/log/smswall.log", level="DEBUG")
		self.ym = YateMessenger.YateMessenger()
		self.to_be_handled = to_be_handled

		conf_file = open("/etc/smswall.yaml", "r")
		config_dict = yaml.load("".join(conf_file.readlines()))
		self.conf = smswall.Config(config_dict, self.log)

	def yatecall(self, d):
		if d == "":
			self.app.Output("SMSWall event: empty")
		elif d == "incoming":
			res = self.ym.parse(self.app.params)
			for (tag, re) in self.regexs:
				if (not res.has_key(tag) or not re.match(res[tag])):
					self.app.Output("SMSWall %s did not match" % (tag,))
					self.app.Acknowledge()
					return
			self.app.Output("SMSWall received: " +  self.app.name + " id: " + self.app.id)
			self.log.info("SMSWall received: " +  self.app.name + " id: " + self.app.id)
			self.app.handled = True
			self.app.retval = "202"
			self.app.Acknowledge()

			try:
				sender = self.ym.SR_get("callerid", ("name", res["caller"]))
				recipient = res['vbts_tp_dest_address']
				message = res['vbts_text']
				msg = smswall.Message(sender, recipient, None, message)
				app = smswall.SMSWall(self.conf)
				ys = YateSender(self)
				app.msg_sender = ys
				app.handle_incoming(msg)

			except Exception as e:
				self.app.Output(str(e))

		elif d == "answer":
			self.app.Output("SMSWall Answered: " +  self.app.name + " id: " + self.app.id)
		elif d == "installed":
			self.app.Output("SMSWall Installed: " + self.app.name )
		elif d == "uninstalled":
			self.app.Output("SMSWall Uninstalled: " + self.app.name )
		else:
			self.app.Output("SMSWall event: " + self.app.type )

	def uninstall(self):
		for (msg, pri) in self.to_be_handled:
			self.app.Uninstall(msg)

	def main(self, priority, regexs):
		self.regexs = regexs
		try:
			self.app.Output("SMSWall Starting")

			for msg in to_be_handled:
				self.app.Output("SMSWall Installing %s at %d" % (msg, priority))
				self.log.info("Installing %s at %d" % (msg, priority))
				self.app.Install(msg, priority)

			while True:
				self.app.flush()
				time.sleep(0.1)
		except:
			self.app.Output("Unexpected error:" + str(sys.exc_info()[0]))
			self.close()

	def close(self):
		self.uninstall()
		self.app.close()

def Usage():
	ret = "SMSWall ERROR: Please provide a priority and a regex to match against\n"
	ret += "CMD PRIORITY [FIELD REGEX]?"
	return ret

def Error(app, log):
	err = Usage()
	vbts.app.Output(err)
	vbts.log.error(err)
	exit(2)

if __name__ == '__main__':
	log_loc = "/tmp/SMSWall.log"
	logging.basicConfig(filename=log_loc, level="DEBUG")
	to_be_handled = ["sip.message"]
	vbts = SMSWall(to_be_handled)
	if (len(sys.argv) < 2):
		Error(vbts.app, vbts.log)
	args = sys.argv[1].split("|")
	#if it's not odd length...
	if (len(args) % 2 == 0 or args[0] == ""):
		Error(vbts.app, vbts.log)
	priority = int(args[0])
	args = args[1:]
	pairs = []
	for i in range(len(args)/2):
		i *= 2
		pairs.append((args[i], re.compile(args[i+1])))
	vbts.app.Output("SMSWall filtering: " + str(pairs))
	vbts.main(priority, pairs)
