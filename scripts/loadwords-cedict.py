import os

import dotenv
dotenv.load_dotenv()

print('connecting to db')
import pymongo
dbClient = pymongo.MongoClient(os.environ['mongoconnectstring'])
curDb = dbClient['hanzi']
wordsCol = curDb['words']

#A parser for the CC-Cedict. Convert the Chinese-English dictionary into a list of python dictionaries with "traditional","simplified", "pinyin", and "english" keys.

#Make sure that the cedict_ts.u8 file is in the same folder as this file, and that the name matches the file name on line 13.

#Before starting, open the CEDICT text file and delete the copyright information at the top. Otherwise the program will try to parse it and you will get an error message.

#Characters that are commonly used as surnames have two entries in CC-CEDICT. This program will remove the surname entry if there is another entry for the character. If you want to include the surnames, simply delete lines 59 and 60.

#This code was written by Franki Allegra in February 2020.

import re

PinyinToneMark = {
    0: "aoeiuv\u00fc",
    1: "\u0101\u014d\u0113\u012b\u016b\u01d6\u01d6",
    2: "\u00e1\u00f3\u00e9\u00ed\u00fa\u01d8\u01d8",
    3: "\u01ce\u01d2\u011b\u01d0\u01d4\u01da\u01da",
    4: "\u00e0\u00f2\u00e8\u00ec\u00f9\u01dc\u01dc",
}

def decode_pinyin(s):
    s = s.lower()
    r = ""
    t = ""
    for c in s:
        if c >= 'a' and c <= 'z':
            t += c
        elif c == ':':
            assert t[-1] == 'u'
            t = t[:-1] + "\u00fc"
        else:
            if c >= '0' and c <= '5':
                tone = int(c) % 5
                if tone != 0:
                    m = re.search("[aoeiuv\u00fc]+", t)
                    if m is None:
                        t += c
                    elif len(m.group(0)) == 1:
                        t = t[:m.start(0)] + PinyinToneMark[tone][PinyinToneMark[0].index(m.group(0))] + t[m.end(0):]
                    else:
                        if 'a' in t:
                            t = t.replace("a", PinyinToneMark[tone][0])
                        elif 'o' in t:
                            t = t.replace("o", PinyinToneMark[tone][1])
                        elif 'e' in t:
                            t = t.replace("e", PinyinToneMark[tone][2])
                        elif t.endswith("ui"):
                            t = t.replace("i", PinyinToneMark[tone][3])
                        elif t.endswith("iu"):
                            t = t.replace("u", PinyinToneMark[tone][4])
                        else:
                            t += "!"
            r += t
            t = ""
    r += t
    return r

print('starting')
with open('cedict_ts.u8', encoding = 'utf-8') as file:
    text = file.read()
    lines = text.split('\n')
    dict_lines = list(lines)

#define functions

    def parse_line(line):
        parsed = {}
        if line == '':
            dict_lines.remove(line)
            return 0
        line = line.rstrip('/')
        line = line.split('/')
        if len(line) <= 1:
            return 0
        english = line[1]
        char_and_pinyin = line[0].split('[')
        characters = char_and_pinyin[0]
        characters = characters.split()
        traditional = characters[0]
        simplified = characters[1]
        pinyin = char_and_pinyin[1]
        pinyin = pinyin.rstrip()
        pinyin = pinyin.rstrip("]")
        parsed['traditional'] = traditional
        parsed['simplified'] = simplified
        parsed['pinyin'] = pinyin
        parsed['english'] = english
        list_of_dicts.append(parsed)

    def remove_surnames():
        for x in range(len(list_of_dicts)-1, -1, -1):
            if "surname " in list_of_dicts[x]['english']:
                if list_of_dicts[x]['traditional'] == list_of_dicts[x+1]['traditional']:
                    list_of_dicts.pop(x)
            
    def main():

        #make each line into a dictionary
        #print("Parsing dictionary . . .")
        for line in dict_lines:
                parse_line(line)
        
        #remove entries for surnames from the data (optional):

        #print("Removing Surnames . . .")
        remove_surnames()

        return list_of_dicts


        #If you want to save to a database as JSON objects, create a class Word in the Models file of your Django project:

        # print("Saving to database (this may take a few minutes) . . .")
        # for one_dict in list_of_dicts:
        #     new_word = Word(traditional = one_dict["traditional"], simplified = one_dict["simplified"], english = one_dict["english"], pinyin = one_dict["pinyin"], hsk = one_dict["hsk"])
        #     new_word.save()
        #print('Done!')

list_of_dicts = []
parsed_dict = main()

toInsert = []

for curDef in list_of_dicts:
	decodedPinyin = decode_pinyin(curDef['pinyin'])

	newDef = {}
	newDef['_id'] = curDef['simplified']
	newDef['traditional'] = curDef['traditional']
	newDef['pinyin-numbered'] = curDef['pinyin']
	newDef['pinyin'] = decodedPinyin
	newDef['english'] = curDef['english']

	toInsert.append(newDef)

print(f'inserting {len(toInsert)}')

try:
    wordsCol.with_options(write_concern=pymongo.WriteConcern(w=0)).insert_many(toInsert, ordered=False)
except Exception as e:
    print(str(e))

print('done')