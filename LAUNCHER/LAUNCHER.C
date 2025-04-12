#define STRICT

#include <windows.h>
#include <windowsx.h>

#include <winsock.h>

#include <malloc.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "resource.h"

// some Windows defines backported from win32
#ifndef WM_APP
	#define WM_APP 0x8000
#endif

#ifndef MAX_PATH
	#define MAX_PATH 260
#endif

/* Globals */
// custom dialog event messages
#define WM_HOSTNAME_EVENT (WM_APP + 1)
#define WM_SOCKET_EVENT (WM_APP + 2)

// other limits (incl. trailing NUL)
#define MAX_SERVER 128
#define MAX_USERNAME 32
#define MAX_PASSWORD 32

#define DEFAULT_PORT 14902

// Working directory
char path[MAX_PATH];
char * tenaddr;

/* Window procedure for our main window */
BOOL FAR PASCAL DialogProc(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam)
{
	// static values that should persist across dialogproc message types
	// handles for our dlgbox items
	static HWND hServer, hInfo, hUsername, hPassword, hSavePassword, hPlay;
	// handle for any pending async hostname req
	static HANDLE hHostTask = 0;
	// the address we want to connect to
	static struct sockaddr_in sa = { AF_INET };
	// the socket connecting us to the remote
	static SOCKET sock = INVALID_SOCKET;
	// big reusable buffer, mostly for hostent return (async gethostbyname)
	//  or for packet storage - be careful!
	static char static_buf[MAXGETHOSTSTRUCT];

	switch (msg) {
	case WM_INITDIALOG: {
		int i, count;
		WSADATA wsaData;
		//  This is the maximum length of an INI value...
		char buffer[max(MAX_SERVER, max(MAX_USERNAME, MAX_PASSWORD))];

		// Get handles for all dlg items, useful later
		hServer = GetDlgItem(hWnd, IDC_SERVER);
		hInfo = GetDlgItem(hWnd, IDC_INFO);
		hUsername = GetDlgItem(hWnd, IDC_USERNAME);
		hPassword = GetDlgItem(hWnd, IDC_PASSWORD);
		hSavePassword = GetDlgItem(hWnd, IDC_SAVE_PASSWORD);
		hPlay = GetDlgItem(hWnd, IDC_PLAY);
		
		// INI READING

		// get username and password
		//  assume "save password" ticked if password found
		Edit_LimitText(hUsername, MAX_USERNAME - 1); 
		i = GetPrivateProfileString("Launcher", "Username", "", buffer, MAX_USERNAME, tenaddr);
		if (i > 0)
			Edit_SetText(hUsername, buffer);

		Edit_LimitText(hPassword, MAX_PASSWORD - 1); 
		i = GetPrivateProfileString("Launcher", "Password", "", buffer, MAX_PASSWORD, tenaddr);
		if (i > 0) {
			Edit_SetText(hPassword, buffer);
			Button_SetCheck(hSavePassword, TRUE);
		}

		// read up to 100 server entries
		for (count = 0; count < 100; count ++) {
			char keyname[9];
			sprintf(keyname, "Server%u", count);
			i = GetPrivateProfileString("Launcher", keyname, "", buffer, MAX_SERVER, tenaddr);

			if (i > 0)
				ComboBox_AddString(hServer, buffer);
		}

		// if no entries are found, message user and exit
		count = ComboBox_GetCount(hServer);
		if (count == 0) {
			MessageBox(hWnd, "No server entries found in tenaddr.ini file", NULL, MB_ICONSTOP);
			DestroyWindow(hWnd);
			return TRUE;
		}

		// set the combo box index
		i = GetPrivateProfileInt("Launcher", "Selected", 0, tenaddr);
		ComboBox_SetCurSel(hServer, min(max(0, i), count));

		// initialize Winsock finally
		i = WSAStartup(0x0101, &wsaData);
		if (i != 0) {
			sprintf(buffer, "WSAStartup returned %d", i);
			MessageBox(hWnd, buffer, NULL, MB_ICONSTOP);
			DestroyWindow(hWnd);
			return TRUE;
		} 

		// trigger this message because SetCurSel does not
		PostMessage(hWnd, WM_COMMAND, IDC_SERVER, MAKELONG(hServer, CBN_SELCHANGE));

		return TRUE;
	}

	case WM_COMMAND:
		switch (wParam) {
			case IDC_SERVER:
				if (HIWORD(lParam) == CBN_SELCHANGE) {
					// selection changed, get the new string
					char * token;
					PSTR buffer;
					int i, cbCurSel;
					
					// user had a query in progress, cancel it first
					if (hHostTask != 0) {
						WSACancelAsyncRequest(hHostTask);
						hHostTask = 0;
					}
			
					// user had a socket open, close that too
					if (sock != INVALID_SOCKET) {
						closesocket(sock);
						sock = INVALID_SOCKET;
					}
			
					// reset other dialog state
					Edit_Enable(hUsername, TRUE);
					Edit_Enable(hPassword, TRUE);
					Button_Enable(hPlay, FALSE);

					// alloc room on stack to make the query, then get the text
					cbCurSel = ComboBox_GetCurSel(hServer);
					i = ComboBox_GetLBTextLen(hServer, cbCurSel) + 1;
					buffer = _alloca(i);
					ComboBox_GetLBText(hServer, cbCurSel, buffer);

					// look for a colon in hostname:port
					token = strtok(buffer, ":");
			
					// first part is hostname
					if (token != NULL) {
						// let's turn the servername:port into an IP request
						sprintf(static_buf, "Retrieving server address for %s", token);
						Edit_SetText(hInfo, static_buf);

						hHostTask = WSAAsyncGetHostByName(hWnd, WM_HOSTNAME_EVENT, token, static_buf, sizeof(static_buf));
			
						if (hHostTask != 0) {
							// second part, if set, is port
							token = strtok(NULL, "");
			
							if (token)
								sa.sin_port = htons(atoi(token));
							else
								sa.sin_port = htons(DEFAULT_PORT);
						} else {
							// task failed to start
							sprintf(static_buf, "Error creating server address task: %d", WSAGetLastError());
							Edit_SetText(hInfo, static_buf);
						}
					} // else { shouldn't happen... we tried to block empty strings from the cbox... }
	
					return TRUE;
				}
				break;

			case IDC_USERNAME:
			case IDC_PASSWORD:
				// enable the Play button if the length of these is both > 0 and the socket is valid
				if (HIWORD(lParam) == EN_UPDATE) {
					Button_Enable(hPlay, (Edit_GetTextLength(hUsername) > 0 && Edit_GetTextLength(hPassword) > 0 && sock != INVALID_SOCKET) ? TRUE : FALSE);
					return TRUE;
				}
				break;
				
			case IDC_PLAY:
				if (HIWORD(lParam) == BN_CLICKED) {
					// Send login packet
					int uLen, pLen;

					// Lock button
					Button_Enable(hPlay, FALSE);

					// Check lengths and connection and alloc a packet
					uLen = Edit_GetTextLength(hUsername) + 1;
					pLen = Edit_GetTextLength(hPassword) + 1;
					if (uLen > 1 && pLen > 1 && sock != INVALID_SOCKET) {
						static const char LAUP[4] = { 'L', 'A', 'U', 'P' };
						int allLen = 2 + 4 + 4 + uLen + 4 + pLen;
						char * pktLogin = _alloca(allLen);
						u_long off = 0;

						// prefix
						pktLogin[0] = allLen & 0xFF;
						pktLogin[1] = allLen >> 8;
						memcpy(&pktLogin[2], LAUP, sizeof(LAUP));
						// username
						pktLogin[6] = uLen & 0xFF;
						pktLogin[7] = uLen >> 8;
						pktLogin[8] = pktLogin[9] = 0;
						Edit_GetText(hUsername, &pktLogin[10], uLen);
						// password
						pktLogin[10 + uLen] = pLen & 0xFF;
						pktLogin[11 + uLen] = pLen >> 8;
						pktLogin[12 + uLen] = pktLogin[13 + uLen] = 0;
						Edit_GetText(hPassword, &pktLogin[14 + uLen], pLen);

						// go to blocking mode
						WSAAsyncSelect(sock, hWnd, 0, 0);
						ioctlsocket(sock, FIONBIO, &off);						
						// send the packet!
						if (send(sock, pktLogin, allLen, 0) == allLen) {
							// return to nonblocking
							WSAAsyncSelect(sock, hWnd, WM_SOCKET_EVENT, FD_READ | FD_CLOSE);						

							// do or die... lock the username and password boxes
							Edit_SetText(hInfo, "Logging in...");
	
							Edit_Enable(hUsername, FALSE);
							Edit_Enable(hPassword, FALSE);								
						} else {
							// error sending or remote closed, alert user
							//  this clobbers static_buf but assumption is you can't have
							//  a valid socket w/ an async host req in flight
							sprintf(static_buf, "Server closed connection: %d", WSAGetLastError());
							Edit_SetText(hInfo, static_buf);

							closesocket(sock);
							sock = INVALID_SOCKET;							
						}
					}
					    
					return TRUE;
				}
				break;

		}
		break;

	case WM_HOSTNAME_EVENT:

		// a static_buf has arrived, we have an IP now and can open a conn.
		if (hHostTask != 0 && (HANDLE)wParam == hHostTask) {
			if (WSAGETASYNCERROR(lParam) != 0) {
				// some problem in name resolution!
				sprintf(static_buf, "Error retrieving server address: %hu", WSAGETASYNCERROR(lParam));
				Edit_SetText(hInfo, static_buf);
			} else {
				// get the address from the static_buf req and
				// assemble a struct sockaddr
				HOSTENT *h = (HOSTENT *)static_buf;
				// shouldn't happen, but in testing...
				if (h->h_addr != NULL) {
					sa.sin_addr.s_addr = ((struct in_addr far *)(h->h_addr))->s_addr;

					// all done w/ hostent now
					sprintf(static_buf, "Connecting to server %Fs:%hu", inet_ntoa(sa.sin_addr), ntohs(sa.sin_port));
					Edit_SetText(hInfo, static_buf);
					// Create a SOCKET for connecting to server
					sock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
					// mark it async
					WSAAsyncSelect(sock, hWnd, WM_SOCKET_EVENT, FD_CONNECT | FD_CLOSE);
					// make connection
					connect(sock, (struct sockaddr *) &sa, sizeof(sa));
				} else
					Edit_SetText(hInfo, "Server address request returned NULL");
			}

			// in either case reset the handle
			hHostTask = 0;
		} // else: probably a lingering cancelled task we no longer care about

		return TRUE;

	case WM_SOCKET_EVENT:
		if ((SOCKET)wParam == sock) {
			if (WSAGETSELECTERROR(lParam) != 0) {
				// some problem in connection!
				sprintf(static_buf, "Error retrieving server information: %hu", WSAGETSELECTERROR(lParam));
				Edit_SetText(hInfo, static_buf);

				closesocket(sock);
				sock = INVALID_SOCKET;

				Button_Enable(hPlay, FALSE);
			} else {
				static int pktLen;

				switch (WSAGETSELECTEVENT(lParam)) {
				case FD_CONNECT: {
					// connected!  Send request for info
					static const char getInfo[6] = { 0x06, 0x00, 'L', 'A', 'H', 'I' };
					u_long off = 0;
					Edit_SetText(hInfo, "Retrieving server info...");
					// go to blocking mode
					WSAAsyncSelect(sock, hWnd, 0, 0);
					ioctlsocket(sock, FIONBIO, &off);						
					// send the packet!
					if (send(sock, getInfo, sizeof(getInfo), 0) == sizeof(getInfo)) {
						// and return to nonblocking
						WSAAsyncSelect(sock, hWnd, WM_SOCKET_EVENT, FD_READ | FD_CLOSE);						
						// ready to recv a packet
						pktLen = 0;
	
						// let user hit play, maybe
						Button_Enable(hPlay, (Edit_GetTextLength(hUsername) > 0 && Edit_GetTextLength(hPassword) > 0 && sock != INVALID_SOCKET) ? TRUE : FALSE);
					} else {
						sprintf(static_buf, "Server closed connection: %d", WSAGetLastError());
						Edit_SetText(hInfo, static_buf);

						closesocket(sock);
						sock = INVALID_SOCKET;							
					} 
					break;
				}

				case FD_READ: {
					// a response has arrived.  there are two things we might get here:
					//  a laHI (host info)
					//  a laNI (no init - error!)
					//  a laIN (init OK, get token)
					// we're re-using the static_buf buffer also...
					int to_read, len;

					if (pktLen < 2) {
						// still don't know how much to recv, need 2 bytes
						to_read = 2;
					} else {
						// attempt to fill more in
						to_read = static_buf[0] | (static_buf[1] << 8);
					}

					len = recv(sock, &static_buf[pktLen], to_read - pktLen, 0);

					if (len <= 0) {
						// remote closed connection, or error
						sprintf(static_buf, "Server closed connection: %d", WSAGetLastError());
						Edit_SetText(hInfo, static_buf);
						closesocket(sock);
						sock = INVALID_SOCKET;
						Button_Enable(hPlay, FALSE);
					} else {
						pktLen += len;

						if (pktLen == (static_buf[0] | (static_buf[1] << 8))) {
							// a full pkt!!
							if (static_buf[2] == 'l' && static_buf[3] == 'a') {
								if ((static_buf[4] == 'H' && static_buf[5] == 'I') ||
								    (static_buf[4] == 'N' && static_buf[5] == 'O')) {
									// HI is the server info, NI is the login rejection.
									// In either case the response packet has a message for the user, show it
									u_long infolen = *(u_long *)&static_buf[6];
									Edit_SetText(hInfo, &static_buf[10]);

									Edit_Enable(hUsername, TRUE);
									Edit_Enable(hPassword, TRUE);
								} else if (static_buf[4] == 'O' && static_buf[5] == 'K') {
									// Login accepted by server.  Time to build a tenaddr.ini and launch the game.
									struct LOADPARMS {
									    WORD   segEnv;                  /* child environment  */
									    LPSTR  lpszCmdLine;             /* child command tail */
									    LPWORD lpwShow;                 /* how to show child  */
									    LPWORD lpwReserved;             /* must be NULL       */
									} parms;
										
									HINSTANCE hinstMod;
									WORD awShow[2] = { 2, SW_SHOWNORMAL };
									int infolen;
									char * buffer;

									// done with this now, kill socket
									closesocket(sock);
									sock = INVALID_SOCKET;
									
									// create tenaddr info										
									infolen = (int)(*(u_long *)&static_buf[6]);
									buffer = _alloca(58 + infolen); 
									sprintf(buffer, "type 'ip' address '%Fs' port '%hu' token '%s'", inet_ntoa(sa.sin_addr), ntohs(sa.sin_port), &static_buf[10]);
									
									WritePrivateProfileString("tenfe", "TENFEAVAIL", "1", tenaddr);
									WritePrivateProfileString("Darksun", "ADDRESS", buffer, tenaddr);
									
									// darksun path
									strcpy(static_buf, path);
									strcat(static_buf, "mdark.exe"); 

									parms.segEnv = 0;               /* child inherits environment */
									parms.lpszCmdLine = "";     /* no command line        */
										
									parms.lpwShow = awShow;    /* shows child normally */
									parms.lpwReserved = NULL;  /* must be NULL           */
									
									hinstMod = LoadModule(static_buf, &parms);
	
									if ((UINT) hinstMod < 32) {
									    sprintf(static_buf, "Failed to launch %smdark.exe: %d", path, hinstMod);
									    Edit_SetText(hInfo, static_buf);
									}
									else {
										// we can quit the launcher now
										DestroyWindow(hWnd);
									}																		
								}
							}
							pktLen = 0;
						}
					}

					break;
				}

				case FD_CLOSE:
					sprintf(static_buf, "Server closed connection: %d", WSAGetLastError());
					Edit_SetText(hInfo, static_buf);
					closesocket(sock);
					sock = INVALID_SOCKET;
					Button_Enable(hPlay, FALSE);
				}
			}
		} else {
			// this is an event for a socket we no longer care about.  close it
			closesocket((SOCKET)wParam);
		}

		return TRUE;

	case WM_CLOSE:
		DestroyWindow(hWnd);
		return TRUE;

	case WM_DESTROY: {
		//  This is the maximum length of an INI value...
		char buffer[max(MAX_SERVER, max(MAX_USERNAME, MAX_PASSWORD))];
		int count, i;
		
		// kill any connections etc
		if (sock != INVALID_SOCKET)
			closesocket(sock);

		if (hHostTask != 0)
			WSACancelAsyncRequest(hHostTask);

		WSACleanup();

		// save state of all options to INI
		// write server list
		count = ComboBox_GetCount(hServer);

		if (count > 0) {
			sprintf(buffer, "%d", ComboBox_GetCurSel(hServer));
			WritePrivateProfileString("Launcher", "Selected", buffer, tenaddr);
		} else
			WritePrivateProfileString("Launcher", "Selected", NULL, tenaddr);

		for (i = 0; i < 100; i ++) {
			char keyname[9];
			sprintf(keyname, "Server%u", i);

			if (i < count) {			
				ComboBox_GetLBText(hServer, i, buffer);
				WritePrivateProfileString("Launcher", keyname, buffer, tenaddr);
			} else
				WritePrivateProfileString("Launcher", keyname, NULL, tenaddr);
		}
		
		// also get username and password
		i = Edit_GetText(hUsername, buffer, MAX_USERNAME);
		WritePrivateProfileString("Launcher", "Username", (i > 0 ? buffer : NULL), tenaddr);

		i = Edit_GetText(hPassword, buffer, MAX_PASSWORD);
		WritePrivateProfileString("Launcher", "Password", (i > 0 && Button_GetCheck(hSavePassword) == TRUE ? buffer : NULL), tenaddr);

		// all done!  quit now!
		PostQuitMessage(0);
		return TRUE;
		}
	}

	return FALSE;
}

/* Our application entry point */
int PASCAL WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow)
{
	HWND hWnd;
	BOOL bRet;
	MSG msg;
	int i;

	if (hPrevInstance != NULL) {
		// TODO: raise existing window to top instead of complaining
		MessageBox(NULL, "Application is already running", NULL, MB_ICONSTOP);
		return -1;
	}

	// get the full filepath and trim the exename off the end
	i = GetModuleFileName(hInstance, path, sizeof(path));
	while (i > 0 && path[i - 1] != '\\')
		i --;
	path[i] = '\0';

	// create tenaddr.ini path
	tenaddr = malloc(strlen(path) + strlen("tenaddr.ini") + 1);
	strcpy(tenaddr, path);
	strcat(tenaddr, "tenaddr.ini");

	// create the application dialog
	hWnd = CreateDialog(hInstance,
			MAKEINTRESOURCE(IDD_LAUNCHER),
			0,
			DialogProc);

	if (hWnd == NULL)
		return -1;

	// main loop - try the dialog message handler, then call dlgproc otherwise
	while ((bRet = GetMessage(&msg, 0, 0, 0)) != 0) {
		if (bRet == -1)
			return -1;		

		if (!IsDialogMessage(hWnd, &msg)) {
			TranslateMessage(&msg);
			DispatchMessage(&msg);
		}
	}

	return msg.wParam;
}