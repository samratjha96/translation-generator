from setuptools import setup

setup(name='translator',
      version='1.0',
      description='Translator tool',
      url='http://appian.com',
      packages=['translations', 'translations.extensions'],
      scripts=['bin/translator'],)
