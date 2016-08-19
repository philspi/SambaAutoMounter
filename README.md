# SambaAutoMounter
A python script to automatically mount samba shares as soon as they show up over zeroconf.

# How it works
## Discovering new shares
The discovering mechanism relies on avahis DBus interface, which publishes avai events via the interface *org.freedesktop.Avahi.Server*.
Configured shares are being mounted automatically, whenever a new server that offers a samba service is discovered.
## Mounting shares
Whenever a new configured share is discovered, a configured program is being executed.
For the automount functionality this happens do be *mount.cifs* but could be any other executable you like.
## Unmounting shares
1. On Server loss
   Whenever the avai DBus interface reports the loss of a previously discovered server, the script tries to call the configured unmount command.
   As it is with remote services it is hard to umount a share from a server that is already gone.
   This operation is merely to clean up unreachable mounts via use of the *-f* option to the command *umount.cifs*.
   It is although up to the configuration what executable is being called in the case of a sever shutdown.
2. On *SIGTERM* or *SIGHUP*
   The script tries to unmount all previously mounted shares.
3. On GNOME-Session End
   This basically happens whenever you log out from your desktop.
   Again the script tries to unmount all previously mounted shares.

# Command line
Currently the script only supports one parameter: *-c|--config* to specify the configuration file to use.
It will use *~/.sam/sam.conf* as the default location for the configuraiton file.
```bash
python SambaAutoMounter.py -c sam.conf
```

# Configuration
The configuration is a simple ini-file-style configuration file which is created automatically on startup.
It contains information about the automatically mounted shares as well as infos about logging, mountin, unmounting and maybe more in the Future.
```ini
[services]
# ServiceName with optional login credentials
SampleService = username%password

[fstab]
# ShareName MountLocation fstype MountOptions
//SampleService/*	~/SampleService/*	cifs	username = user,password=pwd,gid=userGroup,uid=userName
//SampleService/SpecialShare	~/SpecialShare	smbfs	username = user,gid=userGroup,uid=userName

[mount_commands]
# Mount commands for each fstype with variables from fstab section
# - SN = ShareName
# - ML = MountLocation
# - MO = MountOptions
cifs = sudo mount.cifs %(SN)s %(ML)s %(MO)s

[unmount_commands]
# Unmount commands for each fstype
# - ML = MountLocation
cifs = sudo umount.cifs %(ML)s

[general]
# Where to log
logfile = /var/log/sam.log

# stdout = Log to stdout instead of file
#logfile = stdout

```

# Additional files
* polkit/org.psp.sam.policy
   A policy kit policy to keep valid authentications for calls pkexec.
   This avoids giving administrative credentials for every managed share when using *pkexec* instead of *sudo* as elevated executor.
   
   The file needs to be put in /usr/share/polkit-1/rules.d/ to be picked up by polkit.
