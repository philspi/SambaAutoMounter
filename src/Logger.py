import time
import sys

class Logger:
	def __init__( self, outfile, print2StdOut ):
		self.outfile = None
		if len( outfile ) > 0:
			if outfile == 'stdout':
				self.outfile = sys.__stdout__
			else:
				self.outfile = open( outfile, "at" )
		self.print2StdOut = print2StdOut

	def setPrint2StdOut( self, print2StdOut ):
		self.print2StdOut = print2StdOut

	def info( self, text ):
		if self.outfile != None or self.print2StdOut:
			message = "%s -> %s"%( time.strftime( "%Y.%m.%d - %H:%M:%S" ), text )
			if self.outfile != None:
				self.outfile.write( message )
				self.outfile.write( "\n" )
				self.outfile.flush()
			if self.print2StdOut:
				print message
