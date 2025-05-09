# Microsoft Visual C++ generated build script - Do not modify

PROJ = LAUNCHER
DEBUG = 0
PROGTYPE = 0
CALLER = 
ARGS = 
DLLS = 
D_RCDEFINES = /d_DEBUG 
R_RCDEFINES = /dNDEBUG 
ORIGIN = MSVC
ORIGIN_VER = 1.00
PROJPATH = C:\MSVC\SOURCE\LAUNCHER\
USEMFC = 0
CC = cl
CPP = cl
CXX = cl
CCREATEPCHFLAG = 
CPPCREATEPCHFLAG = 
CUSEPCHFLAG = 
CPPUSEPCHFLAG = 
FIRSTC = LAUNCHER.C  
FIRSTCPP =             
RC = rc
CFLAGS_D_WEXE = /nologo /G2 /Gy /W3 /Gf /vd0 /Zi /AT /Od /D "_DEBUG" /FR /GA /GEf /Fd"LAUNCHER.PDB"
CFLAGS_R_WEXE = /nologo /Gs /G2 /Gy /W3 /Gf /vd0 /AT /O2 /Ob2 /OV9 /D "NDEBUG" /GA /GEf 
LFLAGS_D_WEXE = /NOLOGO /NOD /PACKC:61440 /FARCALL /ALIGN:16 /ONERROR:NOEXE /CO 
LFLAGS_R_WEXE = /NOLOGO /NOD /PACKC:61440 /FARCALL /ALIGN:16 /ONERROR:NOEXE 
LIBS_D_WEXE = libw oldnames winsock slibcew 
LIBS_R_WEXE = libw oldnames winsock slibcew 
RCFLAGS = /nologo 
RESFLAGS = /nologo 
RUNFLAGS = 
DEFFILE = LAUNCHER.DEF
OBJS_EXT = 
LIBS_EXT = 
!if "$(DEBUG)" == "1"
CFLAGS = $(CFLAGS_D_WEXE)
LFLAGS = $(LFLAGS_D_WEXE)
LIBS = $(LIBS_D_WEXE)
MAPFILE = nul
RCDEFINES = $(D_RCDEFINES)
!else
CFLAGS = $(CFLAGS_R_WEXE)
LFLAGS = $(LFLAGS_R_WEXE)
LIBS = $(LIBS_R_WEXE)
MAPFILE = nul
RCDEFINES = $(R_RCDEFINES)
!endif
!if [if exist MSVC.BND del MSVC.BND]
!endif
SBRS = LAUNCHER.SBR


LAUNCHER_RCDEP = c:\msvc\source\launcher\launcher.ico \
	c:\msvc\source\launcher\launcher.ver


LAUNCHER_DEP = c:\msvc\include\winsock.h


all:	$(PROJ).EXE

LAUNCHER.RES:	LAUNCHER.RC $(LAUNCHER_RCDEP)
	$(RC) $(RCFLAGS) $(RCDEFINES) -r LAUNCHER.RC

LAUNCHER.OBJ:	LAUNCHER.C $(LAUNCHER_DEP)
	$(CC) $(CFLAGS) $(CCREATEPCHFLAG) /c LAUNCHER.C


$(PROJ).EXE::	LAUNCHER.RES

$(PROJ).EXE::	LAUNCHER.OBJ $(OBJS_EXT) $(DEFFILE)
	echo >NUL @<<$(PROJ).CRF
LAUNCHER.OBJ +
$(OBJS_EXT)
$(PROJ).EXE
$(MAPFILE)
c:\msvc\lib\+
c:\msvc\mfc\lib\+
$(LIBS)
$(DEFFILE);
<<
	link $(LFLAGS) @$(PROJ).CRF
	$(RC) $(RESFLAGS) LAUNCHER.RES $@
	@copy $(PROJ).CRF MSVC.BND

$(PROJ).EXE::	LAUNCHER.RES
	if not exist MSVC.BND 	$(RC) $(RESFLAGS) LAUNCHER.RES $@

run: $(PROJ).EXE
	$(PROJ) $(RUNFLAGS)


$(PROJ).BSC: $(SBRS)
	bscmake @<<
/o$@ $(SBRS)
<<
