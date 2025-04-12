Dark Sun Online Launcher
========================

This is a launcher application for Dark Sun Online.  It is intended to replace the previous TEN launcher, handling server selection and login (username / password).

LAUNCHER is a Windows 16-bit application which compiles under MSVC 1.52.  The CFLAGS are set to generate code for Windows in "Protected" mode (Windows 3.0, w/ 80286 or better).

Settings for the launcher are stored in the `tenaddr.ini` file.  A new INI section is added, `[Launcher]`, with keys as follows:

```
[Launcher]
Server0=example.com
Server1=another.example.org
Server2=withport.example.net:12345

Selected=1

Username=username
Password=password
```

On startup, the launcher will open `tenaddr.ini` and populate the list of servers using entries from the file.  Up to 100 servers can be defined (0-99).  The last-used server is read from `Selected` and pre-set on load.  If the server list is empty, the program will exit with an error message instead.

`Username` contains the last-used username.  `Password`, if set, will check the "Remember Password" box and pre-fill the password control.

On exit, settings are written back to the file.


Login
=====
When a server is chosen in the drop-down box, the launcher makes a DNS request and then opens a TCP connection to the server.  On success, it sends a single `laHI` ("Host Info") packet to the server, in the same format as other Dark Sun client communication.  The server responds with a string of information to populate the info box.  This can contain anything, but generally is for a server info / MOTD / player count.

Once connected, the launcher can send a login request to the server by issuing a `laUP` ("Username Password") packet containing the client credentials.  The server should check these against its store and return either `LANI` ("No Init") with an error message in case of problems (unknown user, incorrect password, already logged in, etc).  Or it may respond with `LAIN` ("Init") and a login token.  The launcher updates `tenaddr.ini` with the corresponding info and then executes `mdark.exe`.  DSO uses the login token to connect to the server.


Notes
=====
Though DSO and the server can use zero-compression to reduce packet sizes, this is not (currently) supported for the launcher.  Packets sent from server to launcher must be uncompressed.
