/*
 * tkMacOSXWm.h --
 *
 *	Declarations of Macintosh specific window manager structures.
 *
 * Copyright 2001-2009, Apple Inc.
 * Copyright (c) 2006-2009 Daniel A. Steffen <das@users.sourceforge.net>
 *
 * See the file "license.terms" for information on usage and redistribution of
 * this file, and for a DISCLAIMER OF ALL WARRANTIES.
 */

#ifndef _TKMACWM
#define _TKMACWM

#include "tkMacOSXInt.h"
#include "tkMenu.h"

/*
 * A data structure of the following type holds information for each window
 * manager protocol (such as WM_DELETE_WINDOW) for which a handler (i.e. a Tcl
 * command) has been defined for a particular top-level window.
 */

typedef struct ProtocolHandler {
    Atom protocol;		/* Identifies the protocol. */
    struct ProtocolHandler *nextPtr;
				/* Next in list of protocol handlers for the
				 * same top-level window, or NULL for end of
				 * list. */
    Tcl_Interp *interp;		/* Interpreter in which to invoke command. */
    char* command;		/* Tcl command to invoke when a client message
				 * for this protocol arrives. The actual size
				 * of the structure varies to accommodate the
				 * needs of the actual command. THIS MUST BE
				 * THE LAST FIELD OF THE STRUCTURE. */
} ProtocolHandler;

/* The following data structure is used in the TkWmInfo to maintain a list of all of the
 * transient windows belonging to a given container.
 */

typedef struct Transient {
    TkWindow *winPtr;
    int flags;
    struct Transient *nextPtr;
} Transient;

#define WITHDRAWN_BY_CONTAINER 0x1
#define WITHDRAWN_BY_MASTER 0x1

/*
 * A data structure of the following type holds window-manager-related
 * information for each top-level window in an application.
 */

typedef struct TkWmInfo {
    TkWindow *winPtr;		/* Pointer to main Tk information for this
				 * window. */
    Window reparent;		/* If the window has been reparented, this
				 * gives the ID of the ancestor of the window
				 * that is a child of the root window (may not
				 * be window's immediate parent). If the window
				 * isn't reparented, this has the value
				 * None. */
    Tk_Uid titleUid;		/* Title to display in window caption. If NULL,
				 * use name of widget. */
    char *iconName;		/* Name to display in icon. */
    Tk_Window container;		/* Container window for TRANSIENT_FOR property,
				 * or None. */
    XWMHints hints;		/* Various pieces of information for window
				 * manager. */
    char *leaderName;		/* Path name of leader of window group
				 * (corresponds to hints.window_group).
				 * Malloc-ed. Note: this field doesn't get
				 * updated if leader is destroyed. */
    Tk_Window icon;		/* Window to use as icon for this window, or
				 * NULL. */
    Tk_Window iconFor;		/* Window for which this window is icon, or
				 * NULL if this isn't an icon for anyone. */
    Transient *transientPtr;    /* First item in a list of all transient windows
				 * belonging to this window, or NULL if there
				 * are no transients. */

    /*
     * Information used to construct an XSizeHints structure for the window
     * manager:
     */

    int sizeHintsFlags;		/* Flags word for XSizeHints structure. If the
				 * PBaseSize flag is set then the window is
				 * gridded; otherwise it isn't gridded. */
    int minWidth, minHeight;	/* Minimum dimensions of window, in grid units,
				 * not pixels. */
    int maxWidth, maxHeight;	/* Maximum dimensions of window, in grid units,
				 * not pixels. */
    Tk_Window gridWin;		/* Identifies the window that controls gridding
				 * for this top-level, or NULL if the top-level
				 * isn't currently gridded. */
    int widthInc, heightInc;	/* Increments for size changes (# pixels per
				 * step). */
    struct {
	int x;			/* numerator */
	int y;			/* denominator */
    } minAspect, maxAspect;	/* Min/max aspect ratios for window. */
    int reqGridWidth, reqGridHeight;
				/* The dimensions of the window (in grid units)
				 * requested through the geometry manager. */
    int gravity;		/* Desired window gravity. */

    /*
     * Information used to manage the size and location of a window.
     */

    int width, height;		/* Desired dimensions of window, specified in
				 * grid units. These values are set by the "wm
				 * geometry" command and by ConfigureNotify
				 * events (for when wm resizes window). -1
				 * means user hasn't requested dimensions. */
    int x, y;			/* Desired X and Y coordinates for window.
				 * These values are set by "wm geometry", plus
				 * by ConfigureNotify events (when wm moves
				 * window). These numbers are different than
				 * the numbers stored in winPtr->changes
				 * because (a) they could be measured from the
				 * right or bottom edge of the screen (see
				 * WM_NEGATIVE_X and WM_NEGATIVE_Y flags) and
				 * (b) if the window has been reparented then
				 * they refer to the parent rather than the
				 * window itself. */
    int parentWidth, parentHeight;
				/* Width and height of reparent, in pixels
				 * *including border*. If window hasn't been
				 * reparented then these will be the outer
				 * dimensions of the window, including
				 * border. */
    int xInParent, yInParent;	/* Offset of window within reparent, measured
				 * from upper-left outer corner of parent's
				 * border to upper-left outer corner of child's
				 * border. If not reparented then these are
				 * zero. */
    int configX, configY;	/* x,y position of toplevel when window is
				 * switched into fullscreen state, */
    int configWidth, configHeight;
				/* Dimensions passed to last request that we
				 * issued to change geometry of window. Used to
				 * eliminate redundant resize operations. */

    /*
     * Information about the virtual root window for this top-level, if there
     * is one.
     */

    Window vRoot;		/* Virtual root window for this top-level, or
				 * None if there is no virtual root window
				 * (i.e. just use the screen's root). */
    int vRootX, vRootY;		/* Position of the virtual root inside the root
				 * window. If the WM_VROOT_OFFSET_STALE flag is
				 * set then this information may be incorrect
				 * and needs to be refreshed from the OS. If
				 * vRoot is None then these values are both
				 * 0. */
    unsigned int vRootWidth, vRootHeight;
				/* Dimensions of the virtual root window. If
				 * vRoot is None, gives the dimensions of the
				 * containing screen. This information is never
				 * stale, even though vRootX and vRootY can
				 * be. */

    /*
     * List of children of the toplevel which have private colormaps.
     */

    TkWindow **cmapList;	/* Array of window with private colormaps. */
    int cmapCount;		/* Number of windows in array. */

    /*
     * Miscellaneous information.
     */

    ProtocolHandler *protPtr;	/* First in list of protocol handlers for this
				 * window (NULL means none). */
    Tcl_Obj *commandObj;	/* The command (guaranteed to be a list) for
				 * the WM_COMMAND property. NULL means nothing
				 * available. */
    char *clientMachine;	/* String to store in WM_CLIENT_MACHINE
				 * property, or NULL. */
    int flags;			/* Miscellaneous flags, defined below. */

    /*
     * Macintosh information.
     */

    WindowClass macClass;
    UInt64 attributes, configAttributes;
    TkWindow *scrollWinPtr;	/* Ptr to scrollbar handling grow widget. */
    TkMenu *menuPtr;
    NSWindow *window;

    /*
     * Space to cache current window state when window becomes Fullscreen.
     */

    unsigned long cachedStyle;
    unsigned long cachedPresentation;
    NSRect cachedBounds;

} WmInfo;

/*
 * Flag values for WmInfo structures:
 *
 * WM_NEVER_MAPPED -		non-zero means window has never been mapped;
 *				need to update all info when window is first
 *				mapped.
 * WM_UPDATE_PENDING -		non-zero means a call to UpdateGeometryInfo
 *				has already been scheduled for this window; no
 *				need to schedule another one.
 * WM_NEGATIVE_X -		non-zero means x-coordinate is measured in
 *				pixels from right edge of screen, rather than
 *				from left edge.
 * WM_NEGATIVE_Y -		non-zero means y-coordinate is measured in
 *				pixels up from bottom of screen, rather than
 *				down from top.
 * WM_UPDATE_SIZE_HINTS -	non-zero means that new size hints need to be
 *				propagated to window manager.
 * WM_SYNC_PENDING -		set to non-zero while waiting for the window
 *				manager to respond to some state change.
 * WM_VROOT_OFFSET_STALE -	non-zero means that (x,y) offset information
 *				about the virtual root window is stale and
 *				needs to be fetched fresh from the X server.
 * WM_ABOUT_TO_MAP -		non-zero means that the window is about to be
 *				mapped by TkWmMapWindow. This is used by
 *				UpdateGeometryInfo to modify its behavior.
 * WM_MOVE_PENDING -		non-zero means the application has requested a
 *				new position for the window, but it hasn't
 *				been reflected through the window manager yet.
 * WM_COLORMAPS_EXPLICIT -	non-zero means the colormap windows were set
 *				explicitly via "wm colormapwindows".
 * WM_ADDED_TOPLEVEL_COLORMAP - non-zero means that when "wm colormapwindows"
 *				was called the top-level itself wasn't
 *				specified, so we added it implicitly at the
 *				end of the list.
 * WM_WIDTH_NOT_RESIZABLE -	non-zero means that we're not supposed to
 *				allow the user to change the width of the
 *				window (controlled by "wm resizable" command).
 * WM_HEIGHT_NOT_RESIZABLE -	non-zero means that we're not supposed to
 *				allow the user to change the height of the
 *				window (controlled by "wm resizable" command).
 */

#define WM_NEVER_MAPPED			0x0001
#define WM_UPDATE_PENDING		0x0002
#define WM_NEGATIVE_X			0x0004
#define WM_NEGATIVE_Y			0x0008
#define WM_UPDATE_SIZE_HINTS		0x0010
#define WM_SYNC_PENDING			0x0020
#define WM_VROOT_OFFSET_STALE		0x0040
#define WM_ABOUT_TO_MAP			0x0080
#define WM_MOVE_PENDING			0x0100
#define WM_COLORMAPS_EXPLICIT		0x0200
#define WM_ADDED_TOPLEVEL_COLORMAP	0x0400
#define WM_WIDTH_NOT_RESIZABLE		0x0800
#define WM_HEIGHT_NOT_RESIZABLE		0x1000
#define WM_TOPMOST			0x2000
#define WM_FULLSCREEN			0x4000
#define WM_TRANSPARENT			0x8000

#endif /* _TKMACWM */

/*
 * Local Variables:
 * mode: objc
 * c-basic-offset: 4
 * fill-column: 79
 * coding: utf-8
 * End:
 */
