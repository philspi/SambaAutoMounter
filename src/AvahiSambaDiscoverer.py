import dbus, avahi, gobject
from dbus import DBusException
from dbus.mainloop.glib import DBusGMainLoop

class NullLogger:
	def info( self, *args ):
		pass

class AvahiSambaServiceDiscovererCreater:
	def __init__( self, mounterClass, *args ):
		self.__mounterClass = mounterClass
		self.__args = args

	def __call__( self, systemBus, sessionBus, mainLoop ):
		return self.__mounterClass( systemBus, *self.__args )

# Looks for Samba shares
class AvahiSambaServiceDiscoverer:
	def __init__( self, systemBus, logger ):
		self.logger = logger
		self.server = dbus.Interface( systemBus.get_object(avahi.DBUS_NAME, '/'), 'org.freedesktop.Avahi.Server')
		self.sbrowser = dbus.Interface( 
			systemBus.get_object(avahi.DBUS_NAME, self.server.ServiceBrowserNew(avahi.IF_UNSPEC, avahi.PROTO_UNSPEC, '_smb._tcp', 'local', dbus.UInt32(0))), 
			avahi.DBUS_INTERFACE_SERVICE_BROWSER)
		self.sbrowser.connect_to_signal("ItemNew", self.__onNewItem )
		self.sbrowser.connect_to_signal("ItemRemove", self.__onItemRemoved )

	def __onItemRemoved( self, interface, protocol, name, stype, domain, flags ):
		self.logger.info( "Lost service '%s' type '%s' domain '%s' " % (name, stype, domain) )
		self.onSambaServiceLost( name )

	def __onNewItem( self, interface, protocol, name, stype, domain, flags):

		if flags & avahi.LOOKUP_RESULT_LOCAL:
			self.logger.info( "Found local service '%s' type '%s' domain '%s' " % (name, stype, domain) )
			self.logger.info( "\tSkipping local service" )
		else:
			self.logger.info( "Found remote service '%s' type '%s' domain '%s' " % (name, stype, domain) )
			self.logger.info( "\tResolvin service ..." )
			self.server.ResolveService(interface, protocol, name, stype, 
					domain, avahi.PROTO_UNSPEC, dbus.UInt32(0), 
					reply_handler=self.__onServiceResolved, error_handler=self.__onResolveError)

	def __onServiceResolved( self, *args):
		self.logger.info( '\tSuccessfully resolved service:' )
		self.logger.info( '\t\t%s@%s:%s'%( args[2], args[7], args[8] ) )
		self.onNewSambaService( args[2], args[7], args[8] )

	def __onResolveError( self, message ):
		self.logger.info( "Error while resolving service: " + args[0]  )

	def onNewSambaService( self, name, address, port ):
		pass

	def onSambaServiceLost( self, name ):
		pass

def startDiscovery( discovererClass ):
	loop = DBusGMainLoop( set_as_default=True )
	systemBus = dbus.SystemBus( mainloop=loop )
	sessionBus = dbus.SessionBus( mainloop=loop )
	mainLoop = gobject.MainLoop()
	discoverer = discovererClass( systemBus, sessionBus, mainLoop )
	try:
		mainLoop.run()
	except:
		discoverer.onStop()

if __name__ == "__main__":
	startDiscovery( AvahiSambaServiceDiscovererCreater( AvahiSambaServiceDiscoverer, NullLogger() ) )
