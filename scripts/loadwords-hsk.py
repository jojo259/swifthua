import json
import time
import requests

import os

import dotenv
dotenv.load_dotenv()

print('connecting to db')

import pymongo
dbClient = pymongo.MongoClient(os.environ['mongoconnectstring']).read()
curDb = dbClient['hanzi']
usersCol = curDb['users']
wordsCol = curDb['words']

wordListsToLoad = ['hsk-1', 'hsk-2', 'hsk-3', 'hsk-4', 'hsk-5', 'hsk-6']

def appendToErrorFile(toAppend, printError = True):
	toAppend = str(str(toAppend))

	if printError:
		print(f'	ERROR! {toAppend.encode("utf-8")[:256]}')

	toAppend += '\n\n--------------------------------\n\n'

	with open('errors.txt', 'a', encoding = 'utf-8') as errorsFile:
		errorsFile.write(toAppend)

appendToErrorFile(f'starting {int(time.time())}', False)

toInsert = []

print('starting')
for curListName in wordListsToLoad:
	with open(f'data/{curListName}.json', encoding = 'utf-8') as listFile:
		listFileRead = listFile.read()
		listJson = json.loads(listFileRead)

		curListLen = len(listJson['words'])

		for atWord, curWord in enumerate(listJson['words']):
			try:
				curWordData = curWord["translation-data"]
				
				curWordData['_id'] = curWordData["simplified"]

				curWordData.pop('simplified')

				#print(f'adding list {curListName} {atWord + 1}/{curListLen} word {curWord["translation-data"]["english"]}')

				''' unlicensed
				# get example sentences

				wordData = requests.get(f'https://pinyin-word-api.vercel.app/api/sentences/{curWordSimplified}')
				
				if wordData != None:
					curWordData['sentences'] = wordData.json()

				for curChar in str(curWordData):
					try:
						print(curChar, end = '')
					except:
						print('X', end = '')

				'''

				toInsert.append(curWordData)
			except Exception as e:
				appendToErrorFile(e)

				time.sleep(1)

print(f'inserting {len(toInsert)}')

try:
	wordsCol.with_options(write_concern=pymongo.WriteConcern(w=0)).insert_many(toInsert, ordered=False)
except Exception as e:
	print(str(e))

print('done')