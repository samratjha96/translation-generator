from setuptools import setup

setup(name='translator',
      version='1.0',
      description='Translator tool',
      url='http://appian.com',
      packages=['translations', 'translations.extensions'],
      install_requires=[
            "PyYAML==5.1",
            "jinja2==2.10.3",
            "openpyxl==3.0.0",
            "pandas==0.25.3",
            "termcolor==1.1.0"
      ],
      scripts=['bin/translator'])
