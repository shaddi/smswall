from distutils.core import setup, Extension

setup(name="smswall",
      version="0.0.1",
      description="SMS mailing lists.",
      author="Shaddi Hasan",
      author_email="shaddi@cs.berkeley.edu",
      url="http://cs.berkeley.edu/~shaddi",
      license='bsd',
      packages=['smswall'],
      scripts=['smswall.py'],
      data_files=[('/etc/', ['conf/smswall.yaml'])]
)
