# DarkSunOnline
Reverse engineering the Dark Sun Online: Crimson Sands server

## [Please use the Wiki for most documentation!](https://github.com/greg-kennedy/DarkSunOnline/wiki)
The rest of this document concerns the purpose and goals of this project.

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
**This repository represents a public, open attempt to reverse-engineer a working server for Dark Sun Online: Crimson Sands.** It aims to provide, first, research into the workings of the server application. Eventually, the goal is to produce a standalone server emulator which original era clients can connect to and play.

Currently, there is a Perl script which starts a local listening server, allows a client to connect, and prints packets as they are received. It is not possible to do anything besides pass the initial "Loading..." screen, but demonstrates packet capture for analysis.

As this project is very much in flux, **[the Wiki provides the most in-depth information about the reverse engineering effort](https://github.com/greg-kennedy/DarkSunOnline/wiki)** - please use it to contribute findings about the game, or read more about packet structure and game functionality. As more is discovered about the game, the Wiki should remain up-to-date, and the server can then be built from the collective knowledge.

## How can I help?
Any of these tasks are highest priority:

* A key step is **getting reverse engineering tools working on the DSO .exe file**. DSO is a 16-bit Windows application, but during initialization uses [OpenWatcom's 32-bit DPMI code for Win16](https://github.com/open-watcom/owp4v1copy/blob/master/bld/win386/c/wininit.c) to load the 32-bit binary instead. Ghidra and IDA both fail to handle this correctly, decompiling only the 16-bit portions while leaving the meat of the game executable untouched. A way to convert the 32-bit portion into something RE tools can handle is _essential_ to figuring out correct server responses.
* Figuring out the **packet format** would help. Games typically use a standard format (say, "4 bytes length / 2 bytes type / N bytes payload") throughout - which generally means staring at some binary data until a pattern jumps out.
* There are multiple versions of Dark Sun Online in circulation - beginning with a 1.0 CD-only release, through a timeline with additional features and changes, and culminating in 2.7 (maybe?) during the final days of the service. **We need an archive of client versions,** and some way to track them for uniqueness / versioning / etc. The earliest version includes debug output, while later versions have changes or additional features we'd like to support. The archive could be checked into this repository, but, some sort of curation is needed to manage this project.

If you'd like to get involved, feel free to edit the Wiki, send PRs with additional information, etc.

There is now a [Discord server for development](https://discord.gg/QPfq6t73zY), but note that Discord is _not a place for documentation or public information to be stored_ - it is instead a working-group space for faster paced impermanent conversations. Again, information SHOULD be put onto the Wiki or into the repository, rather than in Discord (pins). Likely this will extend to tech support issues as well, when a server exists: open an Issue rather than asking a question, that way outside users can see the entire conversation.
