# DarkSunOnline
Reverse engineering the Dark Sun Online: Crimson Sands server

## [Please use the Wiki for most documentation!](https://github.com/greg-kennedy/DarkSunOnline/wiki)
The rest of this document concerns the purpose and goals of this project.

## Code
A work-in-progress replacement server is located in the `DSOServer/` subfolder. It requires Python 3. Start the server with `./server.py` (or `python3 server.py`, etc). It listens for connections on TCP port 14902.

The server creates a sqlite3 database on first launch.  Login information (username + password) is stored in a table called `login`, use `manage.py` to edit it or your own preferred sqlite method.

From here, you would connect to the server using your DSO client. (Only one client at a time for now...) The current tested version is 1.0; others may work, but to varying degrees. Edit your `tenaddr.ini` file to point to the IP of your server - if this is local (same machine), use 127.0.0.1. An example might look like:

```ini
[tenfe]
TENFEAVAIL=1

[Darksun]
ADDRESS=type 'ip' address '192.168.0.2' port '14902' token 'abcd1234'
```

The `token` value is a unique ID that the login server issues to the client - for now, it is not checked, and you can put basically anything here. Once done you may try launching `MDARK.EXE` and hopefully connect. An easier way to manage `tenaddr.ini` is provided in the `LAUNCHER/` folder, a Win16 application that presents a server browser and triggers the game to execute once logged in.  The username is currently hard-coded to `username` and password `password`, proper login is planned for later.

Some unit tests in the `tests` folder exercise packet RLE compression/decompression: run `pytest` from the root folder to validate the code.

## Overview
[Dark Sun Online: Crimson Sands](https://en.wikipedia.org/wiki/Dark_Sun_Online:_Crimson_Sands) was an early MMORPG released in 1996 for Windows 95 systems. Playing the game required an active subscription to the Total Entertainment Network ("TEN"), a paid gaming service which provided always-on servers and matchmaking for players. The game itself used a hybrid system of a centralized server for coordination, but direct peer-to-peer connection between clients as a means to reduce server load. TEN itself functioned as an authorization service for DSO (turning logged-in TEN players into account numbers for the `tenaddr.ini` file), but otherwise had little to do with the game functions or networking.

A [postmortem in Game Developer Magazine](https://www.gamedeveloper.com/design/postmortem-ssi-s-i-dark-sun-online-crimson-sands-i-) covers the development process, as well as the repercussions of the game's architecture choices. SSI owned and developed the game, initially slated for the AT&T Interchange network. For the networking portion, the developers subcontracted to the studio "Junglevision", who built large portions of the game engine that SSI developers then added scripted assets onto.

The game officially shut down in 1999. shortly after the dissolution of TEN. No public release of server code nor binaries have been made available. Further complicating matters, no packet logs of client-server interaction seem to exist either.

Since then, occasional efforts have been made to revive the game in some fashion:
* ["Dark Sun World"](https://web.archive.org/web/20090228014403/http://darksunworld.com:80/), active from 2004 until around 2008. This version used the original server binaries from TEN - possibly even a former employee using a "borrowed" server - and continued operating them for some time, but never released them after shutdown either.
* A short attempt in the late 2010s to revive the game on a scratch-built server emulator. The creators reached out to WotC for permission and guidance; instead, [they received a cease-and-desist letter](https://www.reddit.com/r/DarkSun/comments/8sgr8f/comment/e1yuan0/). No trace of this remains.
* At least one other developer is working on a server emulator, with progress [posted to their YouTube channel](https://www.youtube.com/channel/UC_VNdihpbfm7agJ9XnAbgqw). There is no public source code available.

And see also:
* PaulOfTheWest's [Sol Oscuro project](https://gitea.com/paulofthewest/soloscuro), which is aimed at creating a modern engine for the Dark Sun I and II games - both single-player MS-DOS applications that pre-date the Online version, but share common data formats. This project has mature support for reading .gff files and parsing a number of script / trigger formats, maps, etc.

## What's Here
**This repository represents a public, open attempt to reverse-engineer a working server for Dark Sun Online: Crimson Sands.** It aims to provide, first, research into the workings of the client (and theoretical server) application. Eventually, the goal is to produce a standalone server emulator which original era clients can connect to and play.

Currently, there is a Python module which starts a local listening server, allows a client to connect, and handles some of the packets. Enough support exists for an initial login, character creation, and the ability to start the game and walk around the world a bit. Multiple players do not yet work, nor does combat or much of the other aspects of the game.

As this project is very much in flux, **[the Wiki provides the most in-depth information about the reverse engineering effort](https://github.com/greg-kennedy/DarkSunOnline/wiki)** - please use it to contribute findings about the game, or read more about packet structure and game functionality. As more is discovered about the game, the Wiki should remain up-to-date, and the server can then be built from the collective knowledge.

## How can I help?
Any of these tasks are highest priority:

* If you know anything about **reverse engineering** and x86 assembly: read the [disassembly notes](https://github.com/greg-kennedy/DarkSunOnline/wiki/Client-Disassembly) to get started analysing the client code. The 1.0 client includes debug symbols (!) incl. function and variable names, which is a huge head start in tracing program flow.
* There are multiple versions of Dark Sun Online in circulation - beginning with a 1.0 CD-only release, through a timeline with additional features and changes, and culminating in 2.7 (maybe?) during the final days of the service. **We need an archive of client versions,** and some way to track them for uniqueness / versioning / etc. The earliest version includes debug output, while later versions have changes or additional features we'd like to support. The archive could be checked into this repository, but, some sort of curation is needed to manage this project.
* **Testing** is welcome, though many of the issues are obvious currently ("pressing the Player List button crashes the game") - as more of the bigger gaps are filled in, new edge cases will pop up all the time. Anyone with a memory of playing the game "back in the day" is probably helpful as well, to make sure things work as they used to!

If you'd like to get involved, feel free to edit the Wiki, send PRs with additional information, etc.

There is now a [Discord server for development](https://discord.gg/QPfq6t73zY), but note that Discord is _not a place for documentation or public information to be stored_ - it is instead a working-group space for faster paced impermanent conversations. Again, information SHOULD be put onto the Wiki or into the repository, rather than in Discord (pins). Likely this will extend to tech support issues as well, when a server exists: open an Issue rather than asking a question, that way outside users can see the entire conversation.
