# SambaAutoMounter
Automatically mounts samba shares as soon as they show up over zeroconf.

More documentation to come ...

## About files
* polkit/org.psp.sam.policy
...A policy kit policy to keep a valid authentication for calls to /usr/bin/mount and /usr/bin/umount via pkexec.
...This avoids typing in the Admin-Password for every managed share.
...The file needs to be put in /usr/share/polkit-1/rules.d/ to be picked up by polkit.
