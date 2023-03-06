import os

import dotenv
dotenv.load_dotenv()

print('connecting to db')

import pymongo
dbClient = pymongo.MongoClient(os.environ['mongoconnectstring'])
curDb = dbClient['hanzi']
usersCol = curDb['users']
listsCol = curDb['lists']
wordsCol = curDb['words']

baseUrl = 'https://www.swifthua.com'

print('starting')

with open('sitemap.txt', 'a', encoding = 'utf-8') as siteMapFile:

	linesAdded = 0

	def addLine(addStr):
		global linesAdded
		if linesAdded >= 50_000:
			return
		siteMapFile.write(baseUrl + addStr + '\n')
		linesAdded += 1

	addLine('')
	addLine('/go')
	addLine('/lists')
	addLine('/settings')
	addLine('/login')

	for curUser in usersCol.find():

		curUsernameOrIp = curUser.get('_id')

		if curUsernameOrIp == None:
			continue

		if not '.' in curUsernameOrIp and not ':' in curUsernameOrIp:

			addLine('/profile/' + curUsernameOrIp)

	for curList in listsCol.find():

		curListName = curList.get('_id')

		addLine('/list/' + curListName)

	for curWord in wordsCol.find():

		curWordSimplified = curWord.get('_id')

		addLine('/word/' + curWordSimplified)

print('done')