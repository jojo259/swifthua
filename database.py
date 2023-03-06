import config

print('connecting to db')
import pymongo
dbClient = pymongo.MongoClient(config.mongoConnectString)
curDb = dbClient['hanzi']
usersCol = curDb['users']
wordsCol = curDb['words']
listsCol = curDb['lists']
listEditsCol = curDb['listedits']
print('connected to db')