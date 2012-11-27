from distutils.core import setup, Extension

setup(name="smswall",
      version="0.0.1",
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
                  ('/usr/local/share/yate/scripts/', ['yate/Yate_SMSWall.py']),
                  ('/usr/local/share/yate/sounds/', ['sounds/info-recording.gsm'])]
)
