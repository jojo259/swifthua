import os

import dotenv
dotenv.load_dotenv()

debugMode = False

if 'debug' in os.environ:
	debugMode = True
	print('running in DEBUG mode')
else:
	print('running in PRODUCTION mode')

mongoConnectString = os.environ['mongoconnectstring']
jwtSecretKey = os.environ['jwtsecretkey']
discordWebhookUrl = os.environ['discordwebhookurl']