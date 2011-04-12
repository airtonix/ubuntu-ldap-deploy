import os

def makedir( path ):
	try :
		os.makedirs( path )
	except:
		pass

