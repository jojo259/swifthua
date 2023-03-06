import requests
import config

def sendDiscord(toSend, hookUrl):
	def sendDiscordPart(partToSend):
		jsonData = {}
		jsonData['username'] = 'SwiftHua'
		jsonData['content'] = partToSend
		jsonData['allowed_mentions'] = {'parse': []}

		try:
			requests.post(hookUrl, json = jsonData, headers = {'Content-Type': 'application/json'}, timeout = 10)
		except requests.exceptions.RequestException as e:
			print(f'error sending to discord: {e}')

	for i in range(int(len(toSend) / 2000) + 1):
		sendDiscordPart(toSend[i * 2000:i* 2000 + 2000])