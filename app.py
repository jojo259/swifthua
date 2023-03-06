print()
print('init')

import json
import time
import random
import requests
import datetime
import math
import string
import uuid
import re

import bcrypt

import urllib.parse

import logging
logging.getLogger('werkzeug').setLevel(logging.ERROR) # disable default flask.request messages

import config
import logger
import database
import discordsender
import util
import constants
import ratelimits

import flask
app = flask.Flask(__name__)	

import flask_cors
flask_cors.CORS(app)

import flask_jwt_extended
app.config["JWT_SECRET_KEY"] = config.jwtSecretKey
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = datetime.timedelta(86400 * 7)
jwt = flask_jwt_extended.JWTManager(app)

if not config.debugMode:
	import flask_minify
	flask_minify.minify(app = app, html = True, js = True, cssless = True)

import flask_limiter
rateLimiter = flask_limiter.Limiter(
	util.rateLimiterKeyGen,
	app = app,
	storage_uri = config.mongoConnectString,
	default_limits = '1/day', # to make it obvious when a route is missing an individual ratelimit
	headers_enabled = False,
	on_breach = util.rateLimitExceededResponse,
)

import flask_caching
cacheManager = flask_caching.Cache(app, config = {
	'CACHE_TYPE': 'SimpleCache',
	'CACHE_DEFAULT_TIMEOUT': 1,
})
cacheManager.init_app(app)

print('starting')

@app.route('/', methods = ['GET'])
@rateLimiter.limit(ratelimits.landingPage)
@util.authorizeJwt
def landingPage(curUsername):
	logger.info(0, f'landingPage')

	if curUsername != None:
		logger.info(1, f'user is logged in as {curUsername}, redirecting to study page')
		return flask.redirect("/go", code = 302)

	return flask.render_template('landing.html.jinja')

@app.route('/go', methods = ['GET'])
@rateLimiter.limit(ratelimits.studyPage)
@util.authorizeJwt
def studyPage(curUsername):
	logger.info(0, 'studyPage')

	return flask.render_template('study.html.jinja', onStudyPage = True, flaskData = util.getFlaskData(curUsername))

# REWRITE
@app.route('/profile/<profileUsername>', methods = ['GET'])
@rateLimiter.limit(ratelimits.profilePage)
@util.authorizeJwt
def profilePage(profileUsername, curUsername):
	logger.info(0, 'profilePage')

	def getUserWordCounts():
		userActiveLists = util.getUserActiveLists(profileUsername, userDoc)

		listsGot = database.listsCol.find({'_id': {'$in': userActiveLists}})

		listsDict = {}

		allWordCounts = {'fullylearningtotal': 0, 'fullylearnedtotal': 0, 'learnedtotaldraw': 0, 'learningtotaldraw': 0, 'learnedtotalpronounce': 0, 'learningtotalpronounce': 0, 'learnedtotaldefine': 0, 'learningtotaldefine': 0, 'lists': {}}

		for curList in listsGot:
			listsDict[curList['_id']] = {}
			for curWord in curList['words']:
				listsDict[curList['_id']][curWord] = True

			allWordCounts['lists'][curList['_id']] = {'fullylearning': 0, 'fullylearned': 0, 'learningdraw': 0, 'learningpronounce': 0, 'learningdefine': 0, 'learneddraw': 0, 'learnedpronounce': 0,'learneddefine': 0,}

		for curWord in userDoc.get('words', []):
			curWordStrengthDraw = curWord['wordstrength']['draw']
			curWordStrengthPronounce = curWord['wordstrength']['pronounce']
			curWordStrengthDefine = curWord['wordstrength']['define']

			if curWordStrengthDraw >= constants.learnedStrength:
				allWordCounts[f'learnedtotaldraw'] += 1
			else:
				allWordCounts[f'learningtotaldraw'] += 1

			if curWordStrengthPronounce >= constants.learnedStrength:
				allWordCounts[f'learnedtotalpronounce'] += 1
			else:
				allWordCounts[f'learningtotalpronounce'] += 1

			if curWordStrengthDefine >= constants.learnedStrength:
				allWordCounts[f'learnedtotaldefine'] += 1
			else:
				allWordCounts[f'learningtotaldefine'] += 1

			if curWordStrengthDraw >= constants.learnedStrength and curWordStrengthPronounce >= constants.learnedStrength and curWordStrengthDefine >= constants.learnedStrength: # learned
				fullyCurWordStr = 'learned'
			else:
				fullyCurWordStr = 'learning'

			allWordCounts[f'fully{fullyCurWordStr}total'] += 1

			for curListName in userActiveLists:
				if curListName in allWordCounts['lists']:
					if curWord['simplified'] in listsDict[curListName]:
						allWordCounts['lists'][curListName][f'fully{fullyCurWordStr}'] += 1

						if curWordStrengthDraw >= constants.learnedStrength:
							allWordCounts['lists'][curListName][f'learneddraw'] += 1
						else:
							allWordCounts['lists'][curListName][f'learningdraw'] += 1

						if curWordStrengthPronounce >= constants.learnedStrength:
							allWordCounts['lists'][curListName][f'learnedpronounce'] += 1
						else:
							allWordCounts['lists'][curListName][f'learningpronounce'] += 1

						if curWordStrengthDefine >= constants.learnedStrength:
							allWordCounts['lists'][curListName][f'learneddefine'] += 1
						else:
							allWordCounts['lists'][curListName][f'learningdefine'] += 1

		return allWordCounts

	def getUserWordsDueWhen():
		userWords = userDoc.get('words', [])

		userSettings = util.getUserSettings(profileUsername, userDoc)

		curTime = time.time()
		
		dueDays = {}

		curDay = int(curTime / 86400)

		highestDay = 0
		lowestDay = 99999

		userWords = util.addUserActiveListsToWords(userWords, userSettings)

		for curWord in userWords:
			dueList = []

			wordEnabledTestTypes = util.getWordEnabledTestTypes(curWord, userSettings)

			if 'draw' in wordEnabledTestTypes:
				dueList.append(curWord['due']['draw'])
			if 'pronounce' in wordEnabledTestTypes:
				dueList.append(curWord['due']['pronounce'])
			if 'define' in wordEnabledTestTypes:
				dueList.append(curWord['due']['define'])

			for curDue in dueList:
				curDueDay = max(0, int(curDue / 86400) - curDay)
				if curDueDay > 30:
					continue

				if curDueDay not in dueDays:
					dueDays[curDueDay] = 0
				dueDays[curDueDay] += 1

				if curDueDay > highestDay:
					highestDay = curDueDay

		for i in range(min(highestDay, 33)):
			if i not in dueDays:
				dueDays[i] = 0

		return dueDays

	@cacheManager.memoize(timeout = 10)
	def getUserStrengthsData(userDoc, forAllWords = False, forWords = [], forTests = constants.testTypes):
		logger.info(1, 'getUserStrengthsData')

		strengthsData = []

		strengthsListsDataPointsCount = 0
		strengthsListsTotalCount = 0
		for curWordData in userDoc.get('words', []):
			if forAllWords or curWordData.get('simplified', '') in forWords:
				for testType in forTests:
					testStrengthsList = curWordData.get('strengthslist', {}).get(testType)
					if testStrengthsList != None:
						strengthsListsTotalCount += 1
						toAppend = []
						for strengthDataEpochHour, wordStrength in testStrengthsList.items():
							strengthsListsDataPointsCount += 1
							toAppend.append([int(strengthDataEpochHour) * 3600 * 1000, wordStrength])
						strengthsData.append(toAppend)

		if strengthsListsTotalCount == 0:
			strengthsListsTotalCount = 0.01 # avoid division by 0 error

		logger.info(2, f'there are {strengthsListsTotalCount} strengths lists with {strengthsListsDataPointsCount} total data points')
		logger.info(2, f'the strengths lists have an average of {int(strengthsListsDataPointsCount / strengthsListsTotalCount * 10) / 10} data points')

		return strengthsData

	userDoc = database.usersCol.find_one({'_id': profileUsername})

	if userDoc == None:
		return 'user not found'

	userAllStrengthsData = getUserStrengthsData(userDoc, forAllWords = True)

	# get and save some statistics

	userWordCounts = getUserWordCounts()
	curTime = time.time()
	timeLabel = int(curTime)
	database.usersCol.update_one({'_id': profileUsername}, {'$set': {f'stats.{util.getEpochHour(curTime)}.misc.wordcountsdata': userWordCounts}})

	userCurList = util.getUserCurList(profileUsername, userDoc)

	userActiveLists = util.getUserActiveLists(profileUsername, userDoc)

	userWordsDueWhen = getUserWordsDueWhen()

	userTotalStrengths = util.getUserTotalStrengths(profileUsername, userDoc)

	displayName = util.getUserDisplayName(profileUsername, userDoc)

	return flask.render_template('profile.html.jinja', displayName = displayName, userAllStrengthsData = userAllStrengthsData, userCurList = userCurList, userActiveLists = userActiveLists, userWordCounts = userWordCounts, userWordsDueWhen = userWordsDueWhen, userTotalStrengths = userTotalStrengths, flaskData = util.getFlaskData(curUsername))

@app.route('/settings', methods = ['GET', 'POST'])
@rateLimiter.limit(ratelimits.settingsPage)
@util.authorizeJwt
def settingsPage(curUsername):
	logger.info(0, 'settingsPage')

	if curUsername == None:
		logger.info(1, 'user not logged in so redirecting')
		return flask.redirect("/", code = 302)

	userSettings = util.getUserSettings(curUsername)

	displayName = util.getUserDisplayName(curUsername)

	if flask.request.method == 'GET':
		return flask.render_template('settings.html.jinja', flaskData = util.getFlaskData(curUsername))
	elif flask.request.method == 'POST':
		requestJson = dict(flask.request.form)

		newSettings = {}

		booleanSettings = ['traditional', 'definehard', 'pronouncehard', 'disabletestdraw', 'disabletestdefine', 'disabletestpronounce', 'playqueueaudio']

		for curField in booleanSettings:
			newSettings[curField] = True if requestJson.get(curField) == 'on' else False

		textSettings = ['email', 'discord']

		for curField in textSettings:
			newSettings[curField] = requestJson.get(curField)

		# prevent disabling all tests

		if newSettings['disabletestdraw'] and newSettings['disabletestpronounce'] and newSettings['disabletestdefine']:
			return flask.render_template('settings.html.jinja', alertText = 'Cannot disable all test types', alertCol = '#f00', flaskData = util.getFlaskData(curUsername))

		util.setUserSettings(curUsername, newSettings)

		userSettings = util.getUserSettings(curUsername)

		return flask.render_template('settings.html.jinja', alertText = 'Saved settings', alertCol = '#0f0', flaskData = util.getFlaskData(curUsername))

@app.route('/word/<displayWord>', methods = ['GET'])
@rateLimiter.limit(ratelimits.wordPage)
@util.authorizeJwt
def wordPage(displayWord, curUsername):
	logger.info(0, 'wordPage')

	flaskData = util.getFlaskData(curUsername)

	wordDoc = database.wordsCol.find_one({'_id': displayWord})

	if wordDoc == None:
		return 'word not found'

	flaskData['wordDoc'] = wordDoc

	return flask.render_template('word.html.jinja', flaskData = flaskData)

# REWRITE
@app.route('/login', methods = ['GET', 'POST'])
@rateLimiter.limit(ratelimits.loginPage)
@util.authorizeJwt
def loginPage(curUsername):
	logger.info(0, 'loginPage')

	def signedUpResponse():
		authToken = util.getAccessToken(formUsername)
		response = flask.make_response(flask.redirect('/'))
		response.set_cookie('jwt', authToken, max_age = 86400 * 7, httponly = True, secure = True)

		return response

	if curUsername != None:
		logger.info(1, 'user is logged in so redirecting')
		return flask.redirect(f"/profile/{curUsername}", code = 302)

	displayName = util.getUserDisplayName(curUsername)

	if flask.request.method == 'GET':
		return flask.render_template('login.html.jinja', flaskData = util.getFlaskData(curUsername))
	elif flask.request.method == 'POST':
		if 'loginusername' in flask.request.form:
			logger.info(1, 'loginRoute')

			formUsername = flask.request.form.get("loginusername").lower()
			formPassword = flask.request.form.get("loginpassword")

			userDoc = database.usersCol.find_one({'_id': formUsername})
			if userDoc != None:
				userDocPasswordHashed = userDoc['info']['passwordhashed']

				# check if password is correct
				if bcrypt.checkpw(formPassword.encode('utf-8'), userDocPasswordHashed):
					return signedUpResponse()
				else:
					return flask.render_template('login.html.jinja', error = 'Login failed', flaskData = util.getFlaskData(curUsername))
			else:
				return flask.render_template('login.html.jinja', error = 'No user found with that username', flaskData = util.getFlaskData(curUsername))
		else:
			logger.info(1, 'signupRoute')
			formUsername = flask.request.form.get("signupusername")
			formPassword = flask.request.form.get("signuppassword")

			userAlrDoc = database.usersCol.find_one({'_id': formUsername.lower()})
			if userAlrDoc != None:
				return flask.render_template('login.html.jinja', error = 'Username already exists', flaskData = util.getFlaskData(curUsername))

			if len(formUsername) < 3:
				return flask.render_template('login.html.jinja', error = 'Username too short (min. 3 characters)', flaskData = util.getFlaskData(curUsername))

			if len(formUsername) > 16:
				return flask.render_template('login.html.jinja', error = 'Username too long (max. 16 characters)', flaskData = util.getFlaskData(curUsername))

			if len(formPassword) < 3:
				return flask.render_template('login.html.jinja', error = 'Password too short (min. 3 characters)', flaskData = util.getFlaskData(curUsername))

			if len(formPassword) > 16:
				return flask.render_template('login.html.jinja', error = 'Password too long (max. 16 characters)', flaskData = util.getFlaskData(curUsername))

			# check chars in username and password
			usernameAllowedChars = string.ascii_letters + string.digits + '_'
			for curChar in formUsername:
				if curChar not in usernameAllowedChars:
					return flask.render_template('login.html.jinja', error = 'Disallowed characters in username (only a-z, 0-9, and underscores allowed)', flaskData = util.getFlaskData(curUsername))
			
			passwordAllowedChars = string.ascii_letters + string.digits + string.punctuation
			for curChar in formPassword:
				if curChar not in passwordAllowedChars:
					return flask.render_template('login.html.jinja', error = 'Disallowed characters in password', flaskData = util.getFlaskData(curUsername))

			# generate hashed password
			hashedPassword = bcrypt.hashpw(formPassword.encode('utf-8'), bcrypt.gensalt())

			# create user doc
			newUser = {'_id': formUsername.lower(), 'info': {'passwordhashed': hashedPassword, 'displayname': formUsername}, 'words': []}

			# put user doc in database
			database.usersCol.insert_one(newUser)

			return signedUpResponse()

@app.route('/queue', methods = ['GET'])
@rateLimiter.limit(ratelimits.queuePage)
@util.authorizeJwt
def queuePage(curUsername):
	logger.info(0, 'queuePage')

	if curUsername == None:
		logger.info(1, 'user not logged in, redirecting')
		return flask.redirect("/", code = 302)

	userDoc = database.usersCol.find_one({'_id': curUsername})
	userWords = userDoc.get('words', [])

	flaskData = util.getFlaskData(curUsername, userDoc)

	userSettings = util.getUserSettings(curUsername, userDoc)

	userWords = util.addUserActiveListsToWords(userWords, userSettings)

	curTime = time.time()

	queueWords = []

	for curWord in userWords:
		wordEnabledTestTypes = util.getWordEnabledTestTypes(curWord, userSettings)
		for curType in wordEnabledTestTypes:
			curDue = curWord['due'][curType]
			if curDue == 0:
				curDue = curTime
			readableDue = util.prettyTimeStr(curDue)
			queueWords.append({'simplified': curWord['simplified'], 'testtype': curType, 'due': curDue, 'readabledue': readableDue})

	queueWords = sorted(queueWords, key = lambda x: x['due'])[:1024]

	displayName = util.getUserDisplayName(curUsername, userDoc)

	flaskData['queueWords'] = queueWords

	return flask.render_template('queue.html.jinja', flaskData = flaskData)

@app.route('/lists', methods = ['GET'])
@rateLimiter.limit(ratelimits.listsPage)
@util.authorizeJwt
def listsPage(curUsername):
	logger.info(0, 'listsPage')

	@cacheManager.memoize(timeout = 60)
	def getListsData(searchText, atPage):

		listsQuery = {}

		if searchText != None:
			searchText = re.sub('[^' + constants.listNameAllowedChars + ']', '', searchText) # remove disallowed chars from search
			searchText = searchText.lower()
			listsQuery = {'$or': [{'_id': {'$regex': searchText}}, {'displayname': {'$regex': searchText}}]}

		listsGot = database.listsCol.find(listsQuery).sort('creationtime', 1).skip((atPage - 1) * constants.listsPerPage).limit(constants.listsPerPage)

		allLists = {}
		for curList in listsGot:
			allLists[curList['_id']] = len(curList.get('words', []))

		maxPage = math.ceil(database.listsCol.count_documents(listsQuery) / constants.listsPerPage)

		return atPage, maxPage, allLists

	searchText = flask.request.args.get('search', '')
	atPage = int(flask.request.args.get('page', 1))

	atPage, maxPage, allLists = getListsData(searchText, atPage)

	logger.info(1, f'at page {atPage}, search text "{searchText}"')

	return flask.render_template('lists.html.jinja', atPage = atPage, maxPage = maxPage, allLists = allLists, flaskData = util.getFlaskData(curUsername))

@app.route('/list/<listName>/export', methods = ['GET'])
@rateLimiter.limit(ratelimits.listExportPage)
@util.authorizeJwt
def listExportPage(curUsername, listName):
	
	# get words from list

	listDoc = database.listsCol.find_one({'_id': listName})

	if listDoc == None:
		return 'list not found'

	listWords = listDoc.get('words', [])

	# get word docs from list words

	listWords = list(database.wordsCol.find({'_id': {'$in': listWords}}))

	flaskData = util.getFlaskData(curUsername)

	flaskData['wordsList'] = listWords

	return flask.render_template('export.html.jinja', flaskData = flaskData)

@app.route('/list/<listName>', methods = ['GET'])
@rateLimiter.limit(ratelimits.listPage)
@util.authorizeJwt
def listPage(curUsername, listName):
	logger.info(0, 'listPage')

	userDoc = database.usersCol.find_one({'_id': curUsername})

	flaskData = util.getFlaskData(curUsername, userDoc)

	listDoc = database.listsCol.find_one({'_id': listName})

	if listDoc == None:
		return 'list not found'

	userOwnsList = False
	if curUsername == listDoc.get('owner', ''):
		userOwnsList = True

	listWords = listDoc.get('words', [])

	listWordsDictUnadded = {}

	for curWord in database.wordsCol.find({'_id': {'$in': listWords}}):
		listWordsDictUnadded[curWord.get('_id', '')] = curWord

	listWordsDictLearning = {}

	listActive = False

	if userDoc != None:

		# check if list is active

		if listName in userDoc.get('settings', {}).get('activelists', []):
			listActive = True

		# do word organization

		for curWord in userDoc.get('words', []):

			curWordSimplified = curWord.get('simplified', '')

			# check if current word is in this list

			if not curWordSimplified in listWordsDictUnadded.keys():
				continue # word is not in this list

			# check highest test type strength for this word
			
			highestStrength = -1

			for curTestType in constants.testTypes:
				curStrength = curWord.get('wordstrength', {}).get(curTestType, -1)
				if curStrength > highestStrength:
					highestStrength = curStrength

			# check if word is in learning stage

			if highestStrength >= 0: # learning

				listWordsDictLearning[curWordSimplified] = listWordsDictUnadded[curWordSimplified]
				listWordsDictLearning[curWordSimplified]['userData'] = curWord

				# remove from not added dict

				listWordsDictUnadded.pop(curWordSimplified, None)

	flaskData['listName'] = listName
	flaskData['listDisplayName'] = listDoc.get('displayname', listDoc.get('_id', 'error'))
	flaskData['listLength'] = len(listWords)
	flaskData['listWordsDictUnadded'] = listWordsDictUnadded
	flaskData['listWordsDictLearning'] = listWordsDictLearning
	flaskData['userOwnsList'] = userOwnsList
	flaskData['listActive'] = listActive

	return flask.render_template('list.html.jinja', flaskData = flaskData)

@rateLimiter.limit(ratelimits.defaultLimit)
@app.route('/logout', methods = ['GET']) # move into javascript
def logoutPage():
	logger.info(0, 'logoutPage')

	response = flask.redirect('/')
	response.set_cookie('jwt', 'null', expires = 0)

	return response

@app.route('/api/getwords', methods = ['GET'])
@rateLimiter.limit(ratelimits.getWordsRoute)
@util.authorizeJwt
def getWordsRoute(curUsername):
	logger.info(0, 'getWordsRoute')

	curTime = time.time()

	def packageWordDatas(givenWords): # packaged words to be sent to client
		logger.info(1, 'packageWordDatas')

		# get list of simplified words only e.g. ['爱', '小猫', '他'] in order to get word docs from wordsCol

		simplifiedList = []
		for curWord in givenWords:
			if 'simplified' in curWord: # dumb probably todo
				simplifiedList.append(curWord['simplified'])

		# get word docs for those words

		wordDocs = database.wordsCol.find({'_id': {'$in': simplifiedList}})

		# generate dict to store word docs data for later retrieval

		wordsDict = {}
		for curWord in wordDocs:
			wordsDict[curWord['_id']] = curWord

		# process words

		for curWord in givenWords:

			# re-arrange data (next section uses this data in this form, then it is further modified for returning)

			if 'due' in curWord:

				# word is from user words list

				database.wordsColDoc = wordsDict[curWord['simplified']]
				database.wordsColDoc['simplified'] = database.wordsColDoc['_id']

				for curKey in ['english', 'pinyin', 'traditional']:
					curWord[curKey] = database.wordsColDoc[curKey]
			else:

				# word is a database.wordsCol doc

				curWord['lists'] = [userCurList]

				curWord['due'] = {'draw': 0, 'pronounce': 0, 'define': 0, 'tutorial': 0}
				curWord['wordstrength'] = {'draw': 0, 'pronounce': 0, 'define': 0}

				curWord['simplified'] = curWord['_id']

			# extra processing

			curWord['due']['tutorial'] = 0
			curWord['wordstrength']['tutorial'] = 0

			# assign test type to word

			if curWord['due']['draw'] == 0 and curWord['due']['pronounce'] == 0 and curWord['due']['define'] == 0:

				# no due data so new word so test type is tutorial

				curWord['testtype'] = 'tutorial'

				logger.info(2, f'word is new')

			else:

				# word is not a new word

				wordDueTestTypes = getWordDueTestTypes(curWord)

				if len(wordDueTestTypes) > 0:

					# word has some test types that are due

					curWord['testtype'] = random.choice(wordDueTestTypes)
					logger.info(2, f'chose due test type {curWord["testtype"]}')

				else:

					# word does not have any test types that are due, so just choose a random one

					logger.info(2, 'no due test type found so choosing random')

					wordEnabledTestTypes = util.getWordEnabledTestTypes(curWord, userSettings)

					if len(wordEnabledTestTypes) > 0:
						curWord['testtype'] = random.choice(wordEnabledTestTypes)
					else:
						curWord['testtype'] = 'define'

			# further re-arrange data for returning and remove unnecessary data

			curWord['due'] = curWord['due'][curWord['testtype']]
			curWord['wordstrength'] = curWord['wordstrength'][curWord['testtype']]

			curWord.pop('_id', None)

			if curWord['due'] == 0:
				curWord['due'] = curTime

			# add prettified due date strings

			curWord['prettydue'] = util.prettyTimeStr(curWord['due'])
			
			# add character stroke data (simplified or traditional)

			simTraSetting = userSettings['traditional']
			if simTraSetting:
				simTraStr = 'traditional'
			else:
				simTraStr = 'simplified'

			curWord['strokes'] = []
			curWord['svgdatas'] = []

			for curChar in curWord[simTraStr]:

				charData = util.getCharData(curChar)
				curWord['strokes'].append(charData['medians'])
				curWord['svgdatas'].append(charData['strokes'])

		return givenWords

	def getWordDueTestTypes(curWord): # rewrite todo

		wordDueTestTypes = util.getWordEnabledTestTypes(curWord, userSettings = userSettings)

		if 'draw' in wordDueTestTypes:
			if curWord['due']['draw'] > curTime:
				wordDueTestTypes.remove('draw')
		if 'pronounce' in wordDueTestTypes:
			if curWord['due']['pronounce'] > curTime:
				wordDueTestTypes.remove('pronounce')
		if 'define' in wordDueTestTypes:
			if curWord['due']['define'] > curTime:
				wordDueTestTypes.remove('define')

		return wordDueTestTypes

	userSettings = util.getUserSettings(curUsername)

	userCurList = userSettings['curlist']

	database.usersCol.update_one({'_id': util.getCurUsernameOrIp(curUsername)}, {'$inc': {f'stats.{util.getEpochHour(curTime)}.misc.timeswordsgot': 1}}, upsert = True)

	# todo prevent duplicate words being sent (low priority)

	if curUsername == None: # user not logged in so just return random words

		logger.info(1, 'not logged in so returning random words')

		# get random words from list

		listWords = list(database.listsCol.find_one({'_id': 'hsk-1'})['words'])
		randomWords = random.sample(listWords, constants.wordsToSend)

		# get word docs for the random words

		returnWords = []
		for curWord in database.wordsCol.find({'_id': {'$in': randomWords}}):
			returnWords.append(curWord)

		randomWords = packageWordDatas(returnWords)

		return {'success': True, 'message': 'got words', 'words': randomWords}

	# build up list of words to send, from due words then user words then random words

	logger.info(1, 'logged in so returning user-specific words')

	# get initial data

	userDoc = database.usersCol.find_one({'_id': curUsername})
	userSettings = util.getUserSettings(curUsername, userDoc = userDoc)
	userWords = userDoc.get('words', [])

	logger.info(1, f'userWords total len is {len(userWords)}')

	# add active lists to words for later processing

	userWords = util.addUserActiveListsToWords(userWords, userSettings)

	# filter out words that are not due

	userWords = list(filter(lambda x: len(getWordDueTestTypes(x)) > 0, userWords))

	logger.info(1, f'userWords len after filter is {len(userWords)}')

	# shuffle words

	random.shuffle(userWords)

	# only take first X words

	userWords = userWords[:constants.wordsToSend]

	# generate dictionary for later lookups

	queueWordsDict = {}
	for curWord in userWords:
		queueWordsDict[curWord['simplified']] = True

	# check if not enough words were found

	if len(userWords) < constants.wordsToSend:

		# not enough due words were found so need to add more from user words

		neededWordsNum = constants.wordsToSend - len(userWords)

		logger.info(1, f'not enough words so adding {neededWordsNum} more from random user words')

		if len(userDoc.get('words', [])) > 0: # is userDoc.get('words', []) modified by userWords due to reference thingy? todo

			# user has available words to add

			randomUserWords = list(userDoc.get('words', []))
			randomUserWords = random.sample(randomUserWords, min(neededWordsNum, len(randomUserWords)))

			for curWord in randomUserWords:
				if curWord['simplified'] not in queueWordsDict: # only add the word if it is not already added
					userWords.append(curWord)

	logger.info(1, f'userWords len after potentially adding random user words is {len(userWords)}')

	if len(userWords) < constants.wordsToSend:

		# still not enough words so adding random words from current user list

		neededWordsNum = constants.wordsToSend - len(userWords)
		
		logger.info(1, f'not enough words still, adding {neededWordsNum} random words')

		listWords = list(database.listsCol.find_one({'_id': userCurList})['words'])

		randomWords = random.sample(listWords, min(neededWordsNum, len(listWords)))

		for curWord in database.wordsCol.find({'_id': {'$in': randomWords}}):
			userWords.append(curWord)

	# add active lists to words again

	userWords = util.addUserActiveListsToWords(userWords, userSettings)

	packageWordDatas(userWords)

	logger.info(1, f'userWords len at returning is {len(userWords)}') # should always be the correct number at this stage

	return {'success': True, 'message': 'got words', 'words': userWords}

@app.route('/api/completedword', methods = ['POST'])
@rateLimiter.limit(ratelimits.completedWordRoute)
@util.authorizeJwt
def completedWordRoute(curUsername): # too many db calls

	logger.info(0, 'completedWordRoute')

	curTime = time.time()

	requestJson = flask.request.get_json()
	
	completedWord = requestJson['completedword']
	wordProficiency = requestJson['wordproficiency']
	testType = requestJson['testtype']
	extraStudyTime = requestJson['extrastudytime']

	# sanitize inputs

	if testType == 'tutorial':
		testType = 'draw' # tutorial test just counts as a draw test (because you draw the word)

	if testType not in ['draw', 'pronounce', 'define']:
		logger.info(1, 'invalid test type, returning')
		return {'success': False, 'message': 'invalid test type'}

	if wordProficiency not in [1, 2, 3]:
		logger.info(1, 'invalid word proficiency, returning')
		return {'success': False, 'message': 'invalid word proficiency'}

	# logging

	logStr = f'user {curUsername} completed a {testType} test with proficiency {wordProficiency} in {extraStudyTime}s'
	discordsender.sendDiscord(logStr + f' {completedWord}', config.discordWebhookUrl)
	logger.info(1, logStr)

	# increment user's stats using IP if not logged in

	if curUsername == None:
		logger.info(1, 'curUsername is none so not logged in so using ip instead')
		curUsernameOrIp = util.getIp()
	else:
		curUsernameOrIp = curUsername

	epochHour = util.getEpochHour(curTime)

	toInc = {}
	toInc[f'stats.{epochHour}.wordscompleted.total'] = 1
	toInc[f'stats.{epochHour}.wordscompleted.test{testType}'] = 1
	toInc[f'stats.{epochHour}.wordscompleted.prof{wordProficiency}'] = 1
	toInc[f'stats.{epochHour}.wordscompleted.test{testType}prof{wordProficiency}'] = 1
	toInc[f'stats.{epochHour}.misc.studytime'] = min(30, int(extraStudyTime))

	database.usersCol.update_one({'_id': curUsernameOrIp}, {'$inc': toInc}, upsert = True)

	# if user is not logged in then have any words data to save so return

	if curUsername == None:
		logger.info(1, 'user is not logged in so returning')
		return {'success': True, 'message': 'completed word, not logged in'}

	# find word doc for completed word

	wordsDoc = database.wordsCol.find_one({'_id': completedWord})

	if wordsDoc == None:

		# couldn't find word so look for it in traditional form - should probably never happen as client sends word as simplified

		wordsDoc = database.wordsCol.find_one({'traditional': completedWord})
		completedWord = wordsDoc['_id']

		if wordsDoc == None:

			# word was never found so invalid word

			logger.info(1, 'invalid word, returning')

			return {'success': False, 'message': 'invalid word'}

	# find word's current data

	alrWordData = database.usersCol.find_one({'_id': curUsername}, {'_id': 0, 'words': {'$elemMatch': {'simplified': completedWord}}})

	if 'words' in alrWordData:
		alrWordData = alrWordData['words'][0]
	else:
		alrWordData = {} # word does not already exist in user's data

	# get word's current data or set initial values

	wordLastDue = alrWordData.get('due', {}).get(testType, curTime)
	wordStrength = alrWordData.get('wordstrength', {}).get(testType, 0)

	# increment user stats

	toIncExtra = {}
	if wordStrength >= constants.learnedStrength:
		toIncExtra[f'stats.{epochHour}.wordscompleted.maturetotal'] = 1
		toIncExtra[f'stats.{epochHour}.wordscompleted.maturetest{testType}'] = 1
		toIncExtra[f'stats.{epochHour}.wordscompleted.matureprof{wordProficiency}'] = 1
		toIncExtra[f'stats.{epochHour}.wordscompleted.maturetest{testType}prof{wordProficiency}'] = 1

	database.usersCol.update_one({'_id': curUsernameOrIp}, {'$inc': toIncExtra}, upsert = True)

	oldWordStrength = wordStrength # just for logging

	if wordLastDue > curTime:

		# word not due so can only increase word strength A LITTLE but can decrease if not EZ

		logger.info(1, 'word not due')

		if wordProficiency == 3:
			wordStrength = wordStrength + 0.1
		elif wordProficiency == 2:
			wordStrength = wordStrength - 1
		elif wordProficiency == 1:
			wordStrength = wordStrength - 4

	else:

		# word is due

		logger.info(1, 'word is due')

		if wordProficiency == 3: # EZ
			wordStrength += 1
		elif wordProficiency == 2: # OK
			wordStrength -= 1
		elif wordProficiency == 1: # NO
			wordStrength -= 4

	# limit to 1 decimal place and limit to above 0

	wordStrength = math.floor(max(wordStrength, 0) * 10) / 10

	# find when word is next due, do not change due time if word wasn't actually due

	wordNextDue = wordLastDue
	if wordLastDue < curTime:
		wordNextDue = curTime + max(480, (480 - 80 + random.random() * 160) * (2 ** (wordStrength - 1))) # randomness to spread out due times

	# logging

	logger.info(2, f'old word strength: {oldWordStrength}')
	logger.info(2, f'new word strength: {wordStrength}')
	logger.info(2, f'was due:           {util.prettyTimeStr(wordLastDue)}')
	logger.info(2, f'new due time:      {util.prettyTimeStr(wordNextDue)}')

	# generate new word data for database from previous/initial data

	newWordDataForSetOperatorInit = {f'due.{testType}': wordNextDue, f'wordstrength.{testType}': wordStrength, f'strengthslist.{testType}.{util.getEpochHour(curTime)}': wordStrength}

	newWordDataForSetOperator = {}
	for key, value in newWordDataForSetOperatorInit.items():
		newWordDataForSetOperator['words.$.' + key] = value

	incrementedUpdate = database.usersCol.update_one({'_id': curUsername, 'words.simplified': completedWord}, {'$set': newWordDataForSetOperator})
	
	if incrementedUpdate.matched_count == 0:

		# word not in user words, construct new word and push it

		newWordData = util.genUserWordData()

		newWordData['simplified'] = completedWord

		newWordData['due'][testType] = wordNextDue
		newWordData['wordstrength'][testType] = wordStrength

		database.usersCol.update_one({'_id': curUsername}, {'$push': {'words': newWordData}})
		logger.info(1, 'pushed new user word data')

	else:

		logger.info(1, 'set new user word data')

	def getUserCompletedCounts(curUsername):

		userDoc = database.usersCol.find_one({'_id': curUsername}) # re-finds user doc to have up to date data (could just track the new data in code)
		return userDoc.get('stats', {}).get('completedcounts', None)

	# do total word strength data storing for statistics

	totalStrengths = util.getUserTotalStrengths(curUsername)
	completedCounts = getUserCompletedCounts(curUsername)

	dateLabel = int(curTime)
	#database.usersCol.update_one({'_id': curUsername}, {'$set': {f'stats.{epochHour}.strengthsdata': totalStrengths, f'stats.{epochHour}.completedcountsdata': completedCounts}})

	return {'success': True, 'message': 'word completed'}

@app.route('/api/setvolume', methods = ['POST'])
@rateLimiter.limit(ratelimits.setVolumeRoute)
@util.authorizeJwt
def setVolumeRoute(curUsername):

	logger.info(0, 'setVolumeRoute')

	if curUsername == None:
		return {'success': False, 'message': 'set volume failed - not logged in'}

	requestJson = flask.request.get_json()
	newVolume = requestJson.get('newvolume', 2)

	if newVolume not in [0, 1, 2]:
		return {'success': False, 'message': 'set volume failed - invalid value'}

	util.setUserSettings(curUsername, {'volume': newVolume})

	return {'success': True, 'message': 'successfully set volume'}

@app.route('/api/addword', methods = ['POST'])
@rateLimiter.limit(ratelimits.addWordRoute)
@util.authorizeJwt
def addWordRoute(curUsername):

	logger.info(0, 'addWordRoute')

	if curUsername == None:
		return {'success': False, 'message': 'not logged in'}

	userDoc = database.usersCol.find_one({'_id': curUsername})

	requestJson = flask.request.get_json()
	wordToAdd = requestJson.get('wordToAdd')
	fromList = requestJson.get('fromList')

	# if word is None then choose random word

	if wordToAdd == None:

		logger.info(1, 'no word given so choosing random')

		userCurListName = util.getUserCurList(curUsername, userDoc = userDoc)
		fromList = userCurListName

		listDoc = database.listsCol.find_one({'_id': userCurListName})
		listWords = listDoc.get('words', [])

		if len(listWords) == 0:
			return {'success': False, 'message': 'add words failed - no words found in list'}

		# put user's words into dict for later access

		userWordsDict = {}

		for curWord in userDoc.get('words', []):
			userWordsDict[curWord.get('simplified', '')] = True

		# check if word found that isn't already in user's words

		for curListWord in listWords:

			if curListWord not in userWordsDict:

				# word is not already in to user's words

				wordToAdd = curListWord
				break

		# check if a word was found

		if wordToAdd == None:
			return {'success': True, 'message': 'add words failed - no words left in list', 'listFinished': True}

	else:

		logger.info(1, 'word given')

		# word to add has been provided so check if it is real

		wordDoc = database.wordsCol.find_one({'_id': wordToAdd})

		if wordDoc == None:
			return {'success': False, 'message': 'add words failed - invalid word'}

	# add word to user data

	newWordData = util.genUserWordData()

	newWordData['simplified'] = wordToAdd

	database.usersCol.update_one({'_id': curUsername}, {'$push': {'words': newWordData}, '$addToSet': {'settings.activelists': fromList}})
	logger.info(1, 'pushed new user word data')

	return {'success': True, 'message': 'added word', 'wordAdded': wordToAdd, 'listFinished': False}

@app.route('/api/createlist', methods = ['POST'])
@rateLimiter.limit(ratelimits.createListRoute)
@util.authorizeJwt
def createListRoute(curUsername):

	logger.info(0, 'createListRoute')

	curTime = time.time()

	if curUsername == None:
		return {'success': False, 'message': 'not logged in'}

	requestJson = flask.request.get_json()
	listName = requestJson.get('listName', '')

	# generate list's clean name (for document ID)

	listCleanName = ''

	for curChar in listName.lower():
		if curChar in constants.listNameAllowedChars:
			listCleanName += curChar
		elif curChar == ' ':
			listCleanName += '-'
		else:
			listCleanName += 'x'

	if len(listCleanName) < 3:
		return {'success': False, 'message': f'list name "{listCleanName}" too short'}

	listDoc = database.listsCol.find_one({'_id': listCleanName})

	if listDoc != None:
		return {'success': False, 'message': f'list name "{listCleanName}" taken'}

	newListDoc = {'_id': listCleanName, 'displayname': listName, 'owner': curUsername, 'words': [], 'creationtime': curTime}

	database.listsCol.insert_one(newListDoc)

	return {'success': True, 'message': 'list created', 'listName': listCleanName}

@app.route('/api/savelistsettings', methods = ['POST'])
@rateLimiter.limit(ratelimits.saveListSettingsRoute)
@util.authorizeJwt
def saveListSettingsRoute(curUsername):

	logger.info(0, 'saveListSettingsRoute')

	requestJson = flask.request.get_json()
	listName = requestJson.get('listName', '')

	if curUsername == None:
		return {'success': False, 'message': 'not logged in'}

	listDoc = database.listsCol.find_one({'_id': listName})

	if listDoc == None:
		return {'success': False, 'message': f'list does not exist'}

	toPullAll = {}
	toAddToSet = {}

	for curTestType in constants.testTypes:

		curTestType = curTestType

		if requestJson[f'listDisableTest{curTestType.capitalize()}']:
			toAddToSet[f'settings.listsdisable{curTestType}'] = listName
		else:
			toPullAll[f'settings.listsdisable{curTestType}'] = [listName]

	database.usersCol.update_one({'_id': curUsername}, {'$pullAll': toPullAll, '$addToSet': toAddToSet})

	return {'success': True, 'message': f'saved list settings'}

@app.route('/api/deletelist', methods = ['DELETE'])
@rateLimiter.limit(ratelimits.deleteListRoute)
@util.authorizeJwt
def deleteListRoute(curUsername):

	logger.info(0, 'deleteListRoute')

	if curUsername == None:
		return {'success': False, 'message': 'delete list failed - not logged in'}

	requestJson = flask.request.get_json()
	listName = requestJson.get('listName', '')

	listDoc = database.listsCol.find_one({'_id': listName})

	if listDoc == None:
		return {'success': False, 'message': 'delete list failed - list not found'}

	if listDoc.get('owner', '') != curUsername:
		return {'success': False, 'message': 'delete list failed - not owner of list'}

	util.saveListEdit(listName)

	database.listsCol.delete_one({'_id': listName})

	return {'success': True, 'message': 'deleted list'}

@app.route('/api/savelistdisplayname', methods = ['POST'])
@rateLimiter.limit(ratelimits.saveListDisplayNameRoute)
@util.authorizeJwt
def saveListDisplayName(curUsername):

	logger.info(0, 'saveListDisplayName')

	if curUsername == None:
		return {'success': False, 'message': 'list save display name failed - not logged in'}

	requestJson = flask.request.get_json()
	listName = requestJson.get('listName', '')
	listNewDisplayName = requestJson.get('newDisplayName', 'error')

	listDoc = database.listsCol.find_one({'_id': listName})

	if listDoc == None:
		return {'success': False, 'message': 'list save display name failed - list not found'}

	if listDoc.get('owner', '') != curUsername:
		return {'success': False, 'message': 'list save display name failed - not owner of list'}

	database.listsCol.update_one({'_id': listName}, {'$set': {'displayname': listNewDisplayName}})

	return {'success': True, 'message': 'successfuly saved new list display name'}

@app.route('/api/listaddwords', methods = ['POST'])
@rateLimiter.limit(ratelimits.listAddWordsRoute)
@util.authorizeJwt
def listAddWordsRoute(curUsername):

	logger.info(0, 'listAddWordsRoute')

	if curUsername == None:
		return {'success': False, 'message': 'list add words failed - not logged in'}

	requestJson = flask.request.get_json()
	wordsToAdd = requestJson.get('wordsToAdd', [])
	listName = requestJson.get('listName', '')

	listDoc = database.listsCol.find_one({'_id': listName})

	if listDoc == None:
		return {'success': False, 'message': 'list add words failed - list not found'}

	if listDoc.get('owner', '') != curUsername:
		return {'success': False, 'message': 'list add words failed - not owner of list'}

	listWords = listDoc.get('words', [])
	
	# filter words for real words

	wordDocs = database.wordsCol.find({'$or': [{'_id': {'$in': wordsToAdd}}, {'traditional': {'$in': wordsToAdd}}]})

	wordDocsDict = {}

	for curWord in wordDocs:
		wordDocsDict[curWord.get('_id', '')] = curWord

	wordsToAdd = list(filter(lambda x: x in wordDocsDict.keys(), wordsToAdd))

	util.saveListEdit(listName)

	database.listsCol.update_one({'_id': listName}, {'$addToSet': {'words': {'$each': wordsToAdd}}})

	# get new list doc and words

	newListDoc = database.listsCol.find_one({'_id': listName})
	newListWords = newListDoc.get('words', [])

	newWords = list(set(newListWords) - set(listWords))

	newWordsLen = len(newWords)

	return {'success': True, 'message': 'successfully potentially added words', 'count': newWordsLen, 'wordsAdded': newWords}

@app.route('/api/listremoveword', methods = ['POST'])
@rateLimiter.limit(ratelimits.listRemoveWordRoute)
@util.authorizeJwt
def listRemoveWordRoute(curUsername):

	logger.info(0, 'listRemoveWordRoute')

	if curUsername == None:
		return {'success': False, 'message': 'list remove words failed - not logged in'}

	requestJson = flask.request.get_json()
	wordToRemove = requestJson.get('wordToRemove', '')
	listName = requestJson.get('listName', '')

	listDoc = database.listsCol.find_one({'_id': listName})

	if listDoc == None:
		return {'success': False, 'message': 'list remove words failed - list not found'}

	if listDoc.get('owner', '') != curUsername:
		return {'success': False, 'message': 'list remove words failed - not owner of list'}

	listWords = listDoc.get('words', [])
	
	# check if word is in list

	if wordToRemove not in listWords:
		return {'success': False, 'message': 'list remove words failed - word is not in list'}

	util.saveListEdit(listName)

	database.listsCol.update_one({'_id': listName}, {'$pull': {'words': wordToRemove}})

	return {'success': True, 'message': 'successfully removed word'}

@app.route('/api/chooselist', methods = ['POST'])
@rateLimiter.limit(ratelimits.chooseListRoute)
@util.authorizeJwt
def chooseListRoute(curUsername):

	logger.info(0, 'chooseListRoute')

	if curUsername == None:
		return {'success': False, 'message': 'choose list failed - not logged in'}

	requestJson = flask.request.get_json()
	listName = requestJson.get('listName')

	if listName == None:
		return {'success': False, 'message': 'choose list failed - no list specified'}

	listDoc = database.listsCol.find_one({'_id': listName})

	if listDoc == None:
		return {'success': False, 'message': 'choose list failed - list not found'}

	util.setUserSettings(curUsername, {'curlist': listName})

	return {'success': True, 'message': 'successfully chose list'}

@app.route('/sitemap.txt')
@rateLimiter.limit(ratelimits.defaultLimit)
def static_from_root(): # https://stackoverflow.com/a/14625619/3867506
    return flask.send_from_directory(app.static_folder, flask.request.path[1:])

@app.route('/api/getdailystudytime', methods = ['GET'])
@rateLimiter.limit(ratelimits.getDailyStudyTime)
@util.authorizeJwt
def getDailyStudyTime(curUsername, userDoc = None):
	logger.info(0, 'getDailyStudyTime')

	curTime = time.time()

	if curUsername == None:
		logger.info(1, 'no username cannot get daily study time')
		return {'success': False, 'message': 'not logged in'}

	if userDoc == None:
		userDoc = database.usersCol.find_one({'_id': curUsername})

	epochDay = math.floor(curTime / 86400)
	dayFirstEpochHour = epochDay * 24

	totalSeconds = 0

	for epochHour in range(dayFirstEpochHour, dayFirstEpochHour + 24):
		totalSeconds += userDoc.get('stats', {}).get(str(epochHour), {}).get('misc', {}).get('studytime', 0)

	return {'success': True, 'seconds': totalSeconds, 'message': 'got daily study time'}

@app.route('/api/getqueuesize', methods = ['GET'])
@rateLimiter.limit(ratelimits.getQueueSizeRoute)
@util.authorizeJwt
def getQueueSizeRoute(curUsername, userDoc = None):
	logger.info(0, 'getQueueSizeRoute')

	if curUsername == None:
		logger.info(1, 'no username cannot get queue size')
		return {'success': False, 'message': 'not logged in'}

	if userDoc == None:
		userDoc = database.usersCol.find_one({'_id': curUsername})

	curTime = time.time()

	userSettings = util.getUserSettings(curUsername, userDoc)
	enabledTestTypes = []
	for curType in constants.testTypes:
		if not userSettings[f'disabletest{curType}']:
			enabledTestTypes.append(curType)

	queueSize = 0
	nextDue = 9999999999
	dueInHour = 0
	dueInFourHours = 0
	dueInTwelveHours = 0
	dueInTwentyFourHours = 0

	userWords = userDoc.get('words', [])

	userWords = util.addUserActiveListsToWords(userWords, userSettings)
	
	for curWord in userWords:
		if 'due' in curWord: #flatten TODO
			wordEnabledTestTypes = util.getWordEnabledTestTypes(curWord, userSettings)

			for curType in wordEnabledTestTypes:
				curTypeDue = curWord['due'][curType]

				if curTypeDue < curTime:
					queueSize += 1
				if curTypeDue < curTime + 3600:
					dueInHour += 1
				if curTypeDue < curTime + 3600 * 4:
					dueInFourHours += 1
				if curTypeDue < curTime + 3600 * 12:
					dueInTwelveHours += 1
				if curTypeDue < curTime + 3600 * 24:
					dueInTwentyFourHours += 1

				if curTypeDue < nextDue and curTypeDue > curTime:
					nextDue = curTypeDue
		else:
			queueSize += 1

	logger.info(1, f'queuesize is {queueSize} and word next due {util.prettyTimeStr(nextDue)}')

	database.usersCol.update_one({'_id': curUsername}, {'$set': {f'stats.{util.getEpochHour(curTime)}.misc.queuesize': queueSize}})

	return {'success': True, 'message': 'got queue size', 'queuesize': queueSize, 'nextdue': nextDue, 'dueinhour': dueInHour, 'dueinfourhours': dueInFourHours, 'dueintwelvehours': dueInTwelveHours, 'dueintwentyfourhours': dueInTwentyFourHours}

@app.route('/api/getalluserdata', methods = ['GET'])
@rateLimiter.limit(ratelimits.getAllUserDataRoute)
@util.authorizeJwt
def getAllUserDataRoute(curUsername):
	if curUsername == None:
		return {'success': False, 'message': 'not logged in'}

	userDoc = database.usersCol.find_one({'_id': curUsername})
	if 'info' in userDoc.keys():
		userDoc['info'].pop('passwordhashed', '')

	return userDoc

@app.route('/api/test', methods = ['GET'])
@rateLimiter.limit(ratelimits.defaultLimit)
def testRoute():
	logger.info(0, 'testRoute')

	return {'success': True, 'message': 'pong'}

@app.before_request
@util.authorizeJwt
def beforeRequest(curUsername):
	flask.request.id = str(uuid.uuid4())[:8] # assign unique id to flask.request

	# increment ip stats
	if curUsername != None:
		epochHour = math.floor(time.time() / 60 / 60)
		database.usersCol.update_one({'_id': curUsername}, {'$addToSet': {f"info.ips.{str(util.getIp()).replace('.', ',')}": epochHour}}, upsert = True)

@app.after_request
def refresh_expiring_jwts(response): # YOINKED mostly
	try:
		exp_timestamp = flask_jwt_extended.get_jwt()["exp"]
		now = datetime.datetime.now(datetime.timezone.utc)
		target_timestamp = datetime.datetime.timestamp(now + datetime.timedelta(hours = 24))
		if target_timestamp > exp_timestamp:
			access_token = util.getAccessToken(identity = flask_jwt_extended.get_jwt_identity())
			response.set_cookie('jwt', access_token, max_age = 86400 * 7, httponly = True, secure = True)
			logger.info(0, 'updated token')
		return response
	except (RuntimeError, KeyError):
		# Case where there is not a valid JWT. Just return the original response
		return response

@app.route('/favicon.ico')
@rateLimiter.limit(ratelimits.defaultLimit)
def favicon():
	return app.send_static_file('favicon.ico')