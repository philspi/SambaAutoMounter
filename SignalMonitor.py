import signal

class SignalMonitor:
	def __init__( self ):
		signal.signal( signal.SIGHUP, self.__onSigCought )
		signal.signal( signal.SIGTERM, self.__onSigCought )

	def __onSigCought( self, signum, frame ):
		self.onSigCought()

	def onSigCought( self ):
		print "Cought signal"

if __name__ == "__main__":
	import time
	signalMonitor = SignalMonitor()
	while True:
		print "Waiting..."
		time.sleep( 10 )
