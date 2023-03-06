import time
import math
import json
import datetime
import functools

import flask

import config
import database
import logger
import constants

import flask_jwt_extended

def getFlaskData(curUsername, userDoc = None):

	if userDoc == None:
		userDoc = database.usersCol.find_one({'_id': curUsername})

	# gather relevant settings

	userSettings = getUserSettings(curUsername, userDoc)

	userSettingsFieldsToGet = {'volume': 'curVolume', 'traditional': 'useTraditional', 'pronouncehard': 'pronounceHard', 'definehard': 'defineHard', 'disabletestdraw': 'disableTestDraw', 'disabletestpronounce': 'disableTestPronounce', 'disabletestdefine': 'disableTestDefine', 'playqueueaudio': 'playQueueAudio', 'curlist': 'curList', 'discord': 'discord', 'email': 'email', 'listsdisabledraw': 'listsDisableDraw', 'listsdisablepronounce': 'listsDisablePronounce', 'listsdisabledefine': 'listsDisableDefine'}

	sendUserSettings = {}
	for settingsFieldName, newFieldName in userSettingsFieldsToGet.items():
		if settingsFieldName in userSettings:
			sendUserSettings[newFieldName] = userSettings[settingsFieldName]

	displayName = getUserDisplayName(curUsername, userDoc)

	# collate data

	flaskData = {'curUsername': curUsername, 'displayName': displayName, 'userSettings': sendUserSettings}

	return flaskData

def rateLimitExceededResponse(rateLimit):
	return flask.make_response({'success': False, 'message': f'try again later, rate limit exceeded'})

def setUserSettings(curUsername, toSet = {}): # e.g. setUserSettings('jojo', {'volume': 3, 'curlist': 'hsk-2'})
	newToSet = {}

	for key, value in toSet.items():
		newToSet['settings.' + key] = value

	database.usersCol.update_one({'_id': curUsername}, {'$set': newToSet})

def getUserSettings(curUsername, userDoc = None): # re-organize TODO
	if userDoc == None:
		userDoc = database.usersCol.find_one({'_id': curUsername})

	userSettings = {}

	if userDoc != None:
		if 'settings' in userDoc:
			userSettings = userDoc['settings']

	if 'volume' not in userSettings:
		userSettings['volume'] = 2
	if 'traditional' not in userSettings:
		userSettings['traditional'] = False
	if 'pronouncehard' not in userSettings:
		userSettings['pronouncehard'] = False
	if 'definehard' not in userSettings:
		userSettings['definehard'] = False
	
	if 'disabletestdraw' not in userSettings:
		userSettings['disabletestdraw'] = False
	if 'disabletestpronounce' not in userSettings:
		userSettings['disabletestpronounce'] = False
	if 'disabletestdefine' not in userSettings:
		userSettings['disabletestdefine'] = False

	if 'playqueueaudio' not in userSettings:
		userSettings['playqueueaudio'] = False

	if 'curlist' not in userSettings:
		userSettings['curlist'] = 'hsk-1'

	if 'activelists' not in userSettings:
		userSettings['activelists'] = ['hsk-1']
	if 'listsdisabledraw' not in userSettings:
		userSettings['listsdisabledraw'] = []
	if 'listsdisablepronounce' not in userSettings:
		userSettings['listsdisablepronounce'] = []
	if 'listsdisabledefine' not in userSettings:
		userSettings['listsdisabledefine'] = []

	return userSettings

def getUserCurList(curUsername, userDoc = None):

	dummyReturn = 'hsk-1'

	if userDoc == None:
		userDoc = database.usersCol.find_one({'_id': curUsername})

	if userDoc == None:
		return dummyReturn # user doesn't exist (somehow)

	if 'settings' not in userDoc:
		return dummyReturn

	if 'curlist' not in userDoc['settings']:
		return dummyReturn

	return userDoc['settings']['curlist']

def getUserActiveLists(curUsername, userDoc = None):

	dummyReturn = ['hsk-1']

	if userDoc == None:
		userDoc = database.usersCol.find_one({'_id': curUsername})

	if userDoc == None:
		return dummyReturn # user doesn't exist (somehow)

	if 'settings' not in userDoc:
		return dummyReturn

	if 'activelists' not in userDoc['settings']:
		return dummyReturn

	return userDoc['settings']['activelists']

def getUserDisplayName(curUsername, userDoc = None):

	if userDoc == None:
		userDoc = database.usersCol.find_one({'_id': curUsername})

	if userDoc == None:
		return None # user doesn't exist (somehow)

	if 'info' not in userDoc:
		return None

	if 'displayname' not in userDoc['info']:
		return None

	return userDoc['info']['displayname']

def getIp():
	userIp = 0
	if flask.request.environ.get('HTTP_X_FORWARDED_FOR') is None:
		userIp = flask.request.environ['REMOTE_ADDR']
	else:
		userIp = flask.request.environ['HTTP_X_FORWARDED_FOR'] # if behind a proxy
	if ',' in userIp:
		userIp = userIp.split(',')[0]
	return userIp

def shrinkUserData(curUsername):
	logger.info(0, f'shrinking user data for {curUsername}')
	userDoc = database.usersCol.find_one({'_id': curUsername})

	curTime = time.time()

	maxTimes = [[60 * 60 * 24 * 31, 60 * 60 * 24], [60 * 60 * 24 * 7, 60 * 60 * 4], [60 * 60 * 24, 60 * 60], [60 * 60, 60 * 5], [60, 60]]

	toUnset = {}

	if 'stats' in userDoc:
		dataNames = ['strengthsdata', 'queuesizedata', 'completedcountsdata', 'wordcountsdata']

		for curDataName in dataNames:
			if curDataName in userDoc['stats']:
				latestTime = 0

				for dataTime in userDoc['stats'][curDataName]:
					timeDiff = int(dataTime) - latestTime

					deletingPoint = False

					for curMax in maxTimes:
						if int(dataTime) < curTime - curMax[0]:
							if timeDiff < curMax[1]:
								toUnset[f'stats.{curDataName}.{dataTime}'] = True
								deletingPoint = True

							break

					if not deletingPoint:
						latestTime = int(dataTime)

	removingCount = len(toUnset.keys())

	if removingCount > 0:
		logger.info(1, f'removing {removingCount} data points')
		database.usersCol.update_one({'_id': curUsername}, {'$unset': toUnset})

def getUserTotalStrengths(curUsername, userDoc = None):
	if userDoc == None:
		userDoc = database.usersCol.find_one({'_id': curUsername})

	totalStrengths = {'draw': 0, 'pronounce': 0, 'define': 0}

	for curWord in userDoc.get('words', []):
		for curType, curStrength in curWord['wordstrength'].items():
			totalStrengths[curType] += curStrength

	totalStrengths['avg'] = (totalStrengths['draw'] + totalStrengths['pronounce'] + totalStrengths['define']) / 3

	return totalStrengths

def getWordEnabledTestTypes(curWord, userSettings):

	# find word enabled list settings

	wordEnabledTestTypes = []

	for curTestType in constants.testTypes:
		if not userSettings.get(f'disabletest{curTestType}', False):
			for curList in curWord['lists']:
				if curList not in userSettings.get(f'listsdisable{curTestType}', []):
					wordEnabledTestTypes.append(curTestType)
					break

	return wordEnabledTestTypes

def addUserActiveListsToWords(curWords, userSettings):
	activeLists = userSettings.get('activelists', [])

	listsDict = {}

	for curList in database.listsCol.find({'_id': {'$in': activeLists}}):
		curListName = curList['_id']
		listsDict[curListName] = {}
		for curWord in curList.get('words', []):
			listsDict[curListName][curWord] = True

	for curWord in curWords:

		curWord['lists'] = []

		for curListName in listsDict:

			curWordSimplified = ''

			if 'simplified' in curWord:
				curWordSimplified = curWord['simplified']
			elif '_id' in curWord:
				curWordSimplified = curWord['_id']

			if curWordSimplified in listsDict[curListName]:
				curWord['lists'].append(curListName)

	return curWords

def genUserWordData():
	newWordData = {}

	newWordData['simplified'] = ''

	newWordData['timescompleted'] = {}
	newWordData['wordstrength'] = {}
	newWordData['due'] = {}
	newWordData['lastcompleted'] = {}

	for curType in constants.testTypes:
		newWordData['timescompleted'][curType] = 0
		newWordData['wordstrength'][curType] = 0
		newWordData['due'][curType] = 0
		newWordData['lastcompleted'][curType] = 0

	return newWordData

def saveListEdit(listName):
	listDoc = database.listsCol.find_one({'_id': listName})
	listDoc['name'] = listDoc['_id']
	listDoc.pop('_id')
	listDoc['edittime'] = time.time()
	database.listEditsCol.insert_one(listDoc)

def getCharData(charTo):
	return json.loads(open(f'static/hanzi-writer-data-2.0.1/{charTo}.json').read())

def getAccessToken(curUsername):
	return flask_jwt_extended.create_access_token(identity = curUsername, expires_delta = datetime.timedelta(days=7))

def authorizeJwt(f):
	@functools.wraps(f)
	def decorated_function(*args, **kws):
		curJwtCookie = flask.request.cookies.get('jwt')

		if curJwtCookie == None:
			return f(*args, **kws, curUsername = None)

		tokenDecoded = flask_jwt_extended.decode_token(curJwtCookie)

		curUsername = tokenDecoded.get('sub')

		return f(*args, **kws, curUsername = curUsername)
	return decorated_function

def getCurUsernameOrIp(curUsername):
	if curUsername != None:
		return curUsername
	else:
		userIp = getIp()
		return userIp

@authorizeJwt
def rateLimiterKeyGen(curUsername):
	return getCurUsernameOrIp(curUsername)

def getEpochHour(curTime):
	return math.floor(curTime / 3600)
def getEpochDay(curTime):
	return math.floor(curTime / 86400)

def prettyTimeStr(theTime):

	curTime = time.time()

	timeDiff = abs(theTime - curTime)

	timeWord = ''

	if timeDiff < 1:
		return 'right now'
	elif timeDiff < 60:
		timeWord = 'second'
	elif timeDiff < 3600:
		timeWord = 'minute'
		timeDiff /= 60
	elif timeDiff < 86400:
		timeWord = 'hour'
		timeDiff /= 3600
	elif timeDiff < 2678400:
		timeWord = 'day'
		timeDiff /= 86400
	elif timeDiff < 31536000:
		timeWord = 'month'
		timeDiff /= 2678400
	else:
		timeWord = 'year'
		timeDiff /= 31536000

	timeDiff = math.floor(timeDiff)

	if timeDiff > 1:
		timeWord += 's'

	if theTime > curTime:
		return f'in {timeDiff} {timeWord}'
	else:
		return f'{timeDiff} {timeWord} ago'