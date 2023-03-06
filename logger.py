import logging

import flask

import config

indentSpaceCount = 6 # move to environment variables?

# rename levels for nicer formatting
logging.addLevelName(50, 'CRIT')
logging.addLevelName(40, 'EROR')
logging.addLevelName(30, 'WARN')
logging.addLevelName(20, 'INFO')
logging.addLevelName(10, 'DEBU')

logging.basicConfig(level = logging.INFO)

def getLogStr(indentLevel, logStr):
	return f'{flask.request.id} {" " * indentLevel * indentSpaceCount}{logStr}'

def critical(indentLevel, logStr):
	logging.critical(getLogStr(indentLevel, logStr))

def error(indentLevel, logStr):
	logging.error(getLogStr(indentLevel, logStr))

def warning(indentLevel, logStr):
	logging.warning(getLogStr(indentLevel, logStr))

def info(indentLevel, logStr):
	logging.info(getLogStr(indentLevel, logStr))

def debug(indentLevel, logStr):
	logging.debug(getLogStr(indentLevel, logStr))