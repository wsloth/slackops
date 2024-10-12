from setuptools import setup, find_packages

setup(
   name='SlackOps',
   version='1.0',
   description='Automations for Slack',
   author='Wessel Loth',
   author_email='wessel@loth.io',
   packages=find_packages(),  # Automatically find packages
   install_requires=['slack_bolt', 'python-dotenv', 'PyGithub'], #external packages as dependencies
)