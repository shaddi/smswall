from distutils.core import setup, Extension

setup(name="smswall",
      version="0.0.2",
      description="SMS mailing lists.",
      author="Shaddi Hasan",
      author_email="shaddi@cs.berkeley.edu",
      url="http://cs.berkeley.edu/~shaddi",
      license='bsd',
      packages=['smswall'],
      scripts=['smswall-interactive',
               'scripts/make-universal-list.py',
               'scripts/smswall-clean-confirm'],
      data_files=[('/etc/', ['conf/smswall.yaml']),
                  ('/usr/share/freeswitch/scripts/', ['freeswitch/VBTS_SMSWall.py']),
                  ('/etc/freeswitch/chatplan/default/', ['conf/33_smswall.xml'])
                  ]
)
