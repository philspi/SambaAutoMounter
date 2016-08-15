#!/usr/bin/python

import dbus, sys, time
from AvahiSambaDiscoverer import *
from DBusGnomeSessionClient import *
from SignalMonitor import *
from Logger import *
import subprocess, ConfigParser, argparse, sys, os

class AutoMounterCreater:
	def __init__( self, mounterClass, *args ):
		self.__mounterClass = mounterClass
		self.__args = args

	def __call__( self, systemBus, sessionBus, mainLoop ):
		return self.__mounterClass( systemBus, sessionBus, mainLoop, *self.__args )

class SambaMounter( AvahiSambaServiceDiscoverer, DBusGnomeSessionClient, SignalMonitor ):
	def __init__( self, systemBus, sessionBus, mainLoop, config, logger ):
		self.mainLoop = mainLoop
		self.logger = logger
		SignalMonitor.__init__( self )
		AvahiSambaServiceDiscoverer.__init__( self, systemBus, logger )
		DBusGnomeSessionClient.__init__( self, sessionBus, "SambaAutoMounter", logger )
		self.processConfig( config )
		self.managedMounts = {}

	def onSigCought( self ):
		self.onStop();

	def processConfig( self, config ):
		self.logger.info( "Reading configuration ..." )
		self.serviceLogins = {}
		self.shareOptions = {}
		self.mountCommand = {}
		self.mountCommand["cifs"] = "sudo mount.cifs"
		self.unmountCommand = {}
		self.unmountCommand["cifs"] = "sudo umount.cifs"

		if config.has_section("services"):
			for option in config.options("services"):
				self.serviceLogins[ option ] = config.get( "services", option )
				self.logger.info( "Recorded service: %s -> %s"%( option, self.serviceLogins[ option ] ) )
		if config.has_section("fstab"):
			for option in config.options("fstab"):
				parts = option.split("\t")
				shareName = parts[0]
				mountPath = parts[1]
				fsType = parts[2]

				starPos = mountPath.rfind("*")
				if starPos >= 0:
					mountPath = mountPath[:starPos]

				starPos = shareName.rfind("*")
				if starPos >= 0:
					shareName = shareName[ : starPos - 1 ]

				shareElements = shareName.split( "/" )
				if len( parts ) > 3:
					mountOptions = self.normalizeMountOptions( shareElements[2], "%s=%s"%( parts[3], config.get( "fstab", option ) ) )
				else:
					mountOptions = self.normalizeMountOptions( shareElements[2] )

				self.shareOptions[ shareName ] = [ fsType, self.expandPath( mountPath ), mountOptions ]
				self.logger.info( "Recorded mount options: %s -> %s"%( shareName, self.shareOptions[ shareName ] ) )
		if config.has_section("mount_commands"):
			for option in config.options( "mount_commands" ):
				self.mountCommand[ option ] = config.get( "mount_commands", option, raw=True )
				self.logger.info( "Recorded mount command: %s -> %s"%( option, self.mountCommand[ option ] ) )
		if config.has_section("unmount_commands"):
			for option in config.options( "unmount_commands" ):
				self.unmountCommand[ option ] = config.get( "unmount_commands", option, raw=True )
				self.logger.info( "Recorded unmount command: %s -> %s"%( option, self.unmountCommand[ option ] ) )

	def expandPath( self, path ):
		return path.replace("~", os.getenv("HOME") )

	def normalizeMountOptions( self, serviceName, options = None ):
		normalizedOptions = options
		username = ""
		password = ""
		if serviceName in self.serviceLogins:
			parts = self.serviceLogins[ serviceName ].split("%")
			username = parts[0]
			if len( parts ) > 1:
				password = parts[1]
		if options != None and len(username) > 0 or len( password ) > 0:
			containsPwd = False
			containsUser = False
			for pair in options.split(","):
				keyValue = pair.split("=")
				if not containsUser:
					containsUser = keyValue[0] == "username"
				if not containsPwd:
					containsPwd = keyValue[0] == "password"
				if containsPwd and containsUser:
					break
			if not containsPwd and len( password ) > 0:
				normalizedOptions = "%s,password=%s"%( normalizedOptions, password )
			if not containsUser and len( username ) > 0:
				normalizedOptions = "%s,username=%s"%( normalizedOptions, username )
		return normalizedOptions

	def onNewSambaService( self, name, address, port ):
		self.logger.info( "Querying shares from service %s"%name )
		serviceName = "//%s"%name

		mounts = self.getMounts()

		for share in self.getShares( name, address, port ):
			sharePath = "%s/%s"%( serviceName, share )
			mountOptions = None
			if sharePath in self.shareOptions:
				mountOptions = self.shareOptions[ sharePath ]
			elif serviceName in self.shareOptions:
				mountOptions = list( self.shareOptions[ serviceName ] )
				mountOptions[1] = os.path.join( mountOptions[1], share )

			if mountOptions == None:
				self.logger.info( "Skipping unconfigured share: " + sharePath )
			elif mountOptions[0] in self.mountCommand:
				if sharePath in mounts and mountOptions[1] in mounts[ sharePath ]:
					self.logger.info( "Share %s already mounted at %s"%( sharePath, mountOptions[1] ) )
				elif mountOptions[1] in mounts:
					self.logger.info( "Mountpoint %s already in use by %s"%( mountOptions[1], sharePath ) )
				else:
					self.logger.info( "Mounting %s at %s."%( sharePath, mountOptions[1] ) )
					argsReplacement = {'SN': sharePath, 'ML': mountOptions[1], 'MO': mountOptions[2] }
					args = []
					for arg in self.mountCommand[ mountOptions[0] ].split(" "):
						args.append( arg%argsReplacement )

					if not os.path.exists( mountOptions[1] ):
						self.logger.info( "Creating mount location %s"%mountOptions[1] )
						os.makedirs( mountOptions[1] )
					self.logger.info("Mount command: " + str( args ) )
					mountCommand = subprocess.Popen( args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE )
					(stdout,stderr) = mountCommand.communicate()
					if mountCommand.returncode != 0:
						self.logger.info( "Failed to mount %(SN)s at %(ML)s ..."%argsReplacement )
						self.logger.info( "STDOUT:\n%s\nSTDERR:\n%s"%( stdout, stderr ) )
					else:
						self.logger.info( "Recording managed mount %s at %s"%( sharePath, mountOptions[1] ) )
						self.managedMounts[ sharePath ] = (name, mountOptions[1])
			else:
				self.logger.info( "Don't know how to mount shares of type %s"%mountOptions[0] )

		notificationCommand = ['notify-send', 'SambaAutoMounter', '"Processed service: %s"'%name]
		subprocess.Popen( notificationCommand, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE )

	def getMounts( self ):
		mounts = {}
		args = [ "mount" ];
		mountCommand = subprocess.Popen( args, stdout=subprocess.PIPE, stderr=subprocess.PIPE )
		if mountCommand.wait() == 0:
			for line in mountCommand.stdout.readlines():
				parts = line.split(" on ")
				if len(parts) > 0:
					parts2 = parts[1].split(" type ")
					if len( parts2 ) > 0:
						parts3 = parts2[1].split(" ")
						fs = 'unknown'
						if len( parts3 ) > 0:
							fs = parts3[0]
						if not parts[0] in mounts:
							mounts[ parts[0] ] = {}
						mounts[ parts[0] ][ parts2[0] ] = fs
						if not parts2[0] in mounts:
							mounts[ parts2[0] ] = {}
						mounts[ parts2[0] ][ parts[0] ] = fs
		else:
			raise RuntimeError, "Failed to call mount correctly!"
		return mounts

	def onSambaServiceLost( self, name ):
		self.logger.info( "Lost service: " + name )
		self.logger.info( "Unmounting mounted shares ..." )
		mounts = self.getMounts()
		toBeRemoved = []

		for mount in self.managedMounts:
			if mount in mounts: 
				if self.managedMounts[ mount ][0] == name:
					self.logger.info( "Unmounting %s, currently mounted at %s"%( mount, self.managedMounts[ mount ][1] ) )
			else:
				self.logger.info( "%s no longer mounted, removing it from managed mounts"%( mount ) )
				toBeRemoved.append( mount )
		for mount in toBeRemoved:
			self.managedMounts.pop( mount )

	def getShares( self, name, address, port ):
		shares = set()
		args = [ "smbclient","-L", name, "-I", address, "-N", "-g", "-p", str(port) ]
		myArgs = args

		if not name in self.serviceLogins:
			myArgs.append("-U")
			myArgs.append("GUEST")
		else:
			myArgs.append("-U")
			myArgs.append( self.serviceLogins[ name ] )
		smbClient = subprocess.Popen( myArgs, stdout=subprocess.PIPE, stderr=subprocess.PIPE )
		returnCode = smbClient.wait()
		if returnCode == 0:
			for line in smbClient.stdout.readlines():
				parts = line.split( "|" )
				if parts[0] == "Disk":
					shares.add( parts[1] )
		else:
			self.logger.info( "Failed to query shares from service %s@%s:%s due to error: %s"%( name, address, port, str( smbClient.stdout.readlines() ) ) )
		return shares

	def onStop( self ):
		self.logger.info( "Unmounting mounted shares ..." )
		mounts = self.getMounts()

		for mount in self.managedMounts:
			if mount in mounts:
				fs = mounts[ mount ][ self.managedMounts[ mount ][1] ]
				self.logger.info( "Unmounting %s, currently mounted at %s with filesystem %s"%( mount, self.managedMounts[ mount ][1], fs ) )

				argsReplacement = {'SN': mount, 'ML': self.managedMounts[ mount ][1] }
				args = []
				for arg in self.unmountCommand[ fs ].split(" "):
					args.append( arg%argsReplacement )

				unmountCommand = subprocess.Popen( args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE )
				(stdout,stderr) = unmountCommand.communicate()
				if unmountCommand.returncode != 0:
					self.logger.info( "Failed to unmount %{SN}s from %{ML}s ..."%argsReplacement )
					self.logger.info( "STDOUT:\n%s\nSTDERR:\n%s"%( stdout, stderr ) )
			else:
				self.logger.info( "%s no longer mounted"%( mount ) )
		self.logger.info( "Exiting..." )
		self.mainLoop.quit()

def writeInitialConfig( filename ):
	config = ConfigParser.RawConfigParser()
	config.optionxform = str
	config.add_section('services')
	config.add_section('fstab')
	config.add_section('mount_commands')
	config.add_section('general')
	config.set('general', 'logfile', '/var/log/sam.log')
	config.set('services', 'SampleService', 'username%password')
	config.set('fstab', '//SampleService/*\t~/SampleService/*\tcifs\tusername', 'user,password=pwd,gid=userGroup,uid=userName')
	config.set('fstab', '//SampleService/SpecialShare\t~/SpecialShare\tsmbfs\tusername', 'user,gid=userGroup,uid=userName')
	config.set('mount_commands', 'cifs', 'sudo mount.cifs %(SN)s %(ML)s %(MO)s')
	config.set('unmount_commands', 'cifs', 'sudo umount.cifs %(ML)s')

	# Actually writing config to file
	configDir = os.path.dirname( filename )
	if not os.path.exists( configDir ):
		os.makedirs( configDir )
	configFile = open( filename, 'w' )
	if configFile == None:
		raise IOError, 'Failed to open %s for writing initial config'%filename
	config.write( configFile )
	configFile.close()

def readConfig( filename ):
	filename = filename.replace( "~", os.getenv("HOME") )
	if not os.path.exists( filename ):
		writeInitialConfig( filename )
	config = ConfigParser.ConfigParser()
	config.optionxform = str
	config.read( filename )
	return config

if __name__ == "__main__":
	print "Sleeping 5 seconds until session has settled ..."
	time.sleep(5)
	print "Starting up"
	parser = argparse.ArgumentParser( add_help = True )
	parser.add_argument('-c', '--config', help = 'Specifies the configfile to use.', default = '~/.sam/sam.conf' )
	args = parser.parse_args( sys.argv[1:] )

	configuration = readConfig( args.config )

	startDiscovery( AutoMounterCreater( SambaMounter, configuration, Logger( configuration.get('general','logfile'), False ) ) )
