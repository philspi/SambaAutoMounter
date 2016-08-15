import dbus, time

class StdOutPrinter:
	def info( self, message ):
		print message

class DBusGnomeSessionClient:
	def __init__(self, sessionBus, app_id, logger ):
		self.logger = logger
		sm = dbus.Interface( sessionBus.get_object("org.gnome.SessionManager", '/org/gnome/SessionManager'), 'org.gnome.SessionManager')
		client_id = sm.RegisterClient( app_id, str( time.time() ), dbus_interface="org.gnome.SessionManager")
		self.proxy = sessionBus.get_object("org.gnome.SessionManager", client_id, "org.gnome.SessionManager.ClientPrivate")
		self.proxy.connect_to_signal("QueryEndSession", self.__onQueryEndSession )
		self.proxy.connect_to_signal("EndSession", self.__onEndSession )
		self.proxy.connect_to_signal("CancelEndSession", self.__onCancelEndSession )
		self.proxy.connect_to_signal("Stop", self.__onStop )

	def __onStop(self):
		self.onStop()

	def __onCancelEndSession(self):
		self.onCancelEndSession()

	def __onQueryEndSession(self, flags):
		self.proxy.EndSessionResponse( *self.onQueryEndSession( flags ) )

	def __onEndSession(self, flags):
		self.proxy.EndSessionResponse( *self.onEndSession( flags ) )

	def onStop( self ):
		self.logger.info( "Stop()" )

	def onCancelEndSession( self ):
		self.logger.info( "CancelEndSession()" )

	def onQueryEndSession( self, flags ):
		self.logger.info( "QueryEndSession(" + str( flags ) +")" )
		return (True,"")

	def onEndSession(self, flags):
		self.logger.info( "EndSession(" + str( flags ) +")" )
		return (True, "")

if __name__ == "__main__":
	import gobject
	from dbus.mainloop.glib import DBusGMainLoop

	loop = DBusGMainLoop()
	sessionBus = dbus.SessionBus( mainloop=loop )

	client = DBusGnomeSessionClient( sessionBus, "DBusGnomeSessionClient", StdOutPrinter() )

	gobject.MainLoop().run()
