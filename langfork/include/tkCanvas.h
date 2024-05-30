/*
 * tkCanvas.h --
 *
 *	Declarations shared among all the files that implement canvas widgets.
 *
 * Copyright (c) 1991-1994 The Regents of the University of California.
 * Copyright (c) 1994-1995 Sun Microsystems, Inc.
 * Copyright (c) 1998 by Scriptics Corporation.
 *
 * See the file "license.terms" for information on usage and redistribution of
 * this file, and for a DISCLAIMER OF ALL WARRANTIES.
 */

#ifndef _TKCANVAS
#define _TKCANVAS

#ifndef _TK
#include "tk.h"
#endif

#ifndef USE_OLD_TAG_SEARCH
typedef struct TagSearchExpr_s TagSearchExpr;

struct TagSearchExpr_s {
    TagSearchExpr *next;	/* For linked lists of expressions - used in
				 * bindings. */
    Tk_Uid uid;			/* The uid of the whole expression. */
    Tk_Uid *uids;		/* Expresion compiled to an array of uids. */
    int allocated;		/* Available space for array of uids. */
    int length;			/* Length of expression. */
    int index;			/* Current position in expression
				 * evaluation. */
    int match;			/* This expression matches event's item's
				 * tags. */
};
#endif /* not USE_OLD_TAG_SEARCH */

/*
 * The record below describes a canvas widget. It is made available to the
 * item functions so they can access certain shared fields such as the overall
 * displacement and scale factor for the canvas.
 */

typedef struct TkCanvas {
    Tk_Window tkwin;		/* Window that embodies the canvas. NULL means
				 * that the window has been destroyed but the
				 * data structures haven't yet been cleaned
				 * up.*/
    Display *display;		/* Display containing widget; needed, among
				 * other things, to release resources after
				 * tkwin has already gone away. */
    Tcl_Interp *interp;		/* Interpreter associated with canvas. */
    Tcl_Command widgetCmd;	/* Token for canvas's widget command. */
    Tk_Item *firstItemPtr;	/* First in list of all items in canvas, or
				 * NULL if canvas empty. */
    Tk_Item *lastItemPtr;	/* Last in list of all items in canvas, or
				 * NULL if canvas empty. */

    /*
     * Information used when displaying widget:
     */

    int borderWidth;		/* Width of 3-D border around window. */
    Tk_3DBorder bgBorder;	/* Used for canvas background. */
    int relief;			/* Indicates whether window as a whole is
				 * raised, sunken, or flat. */
    int highlightWidth;		/* Width in pixels of highlight to draw around
				 * widget when it has the focus. <= 0 means
				 * don't draw a highlight. */
    XColor *highlightBgColorPtr;
				/* Color for drawing traversal highlight area
				 * when highlight is off. */
    XColor *highlightColorPtr;	/* Color for drawing traversal highlight. */
    int inset;			/* Total width of all borders, including
				 * traversal highlight and 3-D border.
				 * Indicates how much interior stuff must be
				 * offset from outside edges to leave room for
				 * borders. */
    GC pixmapGC;		/* Used to copy bits from a pixmap to the
				 * screen and also to clear the pixmap. */
    int width, height;		/* Dimensions to request for canvas window,
				 * specified in pixels. */
    int redrawX1, redrawY1;	/* Upper left corner of area to redraw, in
				 * pixel coordinates. Border pixels are
				 * included. Only valid if REDRAW_PENDING flag
				 * is set. */
    int redrawX2, redrawY2;	/* Lower right corner of area to redraw, in
				 * integer canvas coordinates. Border pixels
				 * will *not* be redrawn. */
    int confine;		/* Non-zero means constrain view to keep as
				 * much of canvas visible as possible. */

    /*
     * Information used to manage the selection and insertion cursor:
     */

    Tk_CanvasTextInfo textInfo; /* Contains lots of fields; see tk.h for
				 * details. This structure is shared with the
				 * code that implements individual items. */
    int insertOnTime;		/* Number of milliseconds cursor should spend
				 * in "on" state for each blink. */
    int insertOffTime;		/* Number of milliseconds cursor should spend
				 * in "off" state for each blink. */
    Tcl_TimerToken insertBlinkHandler;
				/* Timer handler used to blink cursor on and
				 * off. */

    /*
     * Transformation applied to canvas as a whole: to compute screen
     * coordinates (X,Y) from canvas coordinates (x,y), do the following:
     *
     * X = x - xOrigin;
     * Y = y - yOrigin;
     */

    int xOrigin, yOrigin;	/* Canvas coordinates corresponding to
				 * upper-left corner of window, given in
				 * canvas pixel units. */
    int drawableXOrigin, drawableYOrigin;
				/* During redisplay, these fields give the
				 * canvas coordinates corresponding to the
				 * upper-left corner of the drawable where
				 * items are actually being drawn (typically a
				 * pixmap smaller than the whole window). */

    /*
     * Information used for event bindings associated with items.
     */

    Tk_BindingTable bindingTable;
				/* Table of all bindings currently defined for
				 * this canvas. NULL means that no bindings
				 * exist, so the table hasn't been created.
				 * Each "object" used for this table is either
				 * a Tk_Uid for a tag or the address of an
				 * item named by id. */
    Tk_Item *currentItemPtr;	/* The item currently containing the mouse
				 * pointer, or NULL if none. */
    Tk_Item *newCurrentPtr;	/* The item that is about to become the
				 * current one, or NULL. This field is used to
				 * detect deletions of the new current item
				 * pointer that occur during Leave processing
				 * of the previous current item. */
    double closeEnough;		/* The mouse is assumed to be inside an item
				 * if it is this close to it. */
    XEvent pickEvent;		/* The event upon which the current choice of
				 * currentItem is based. Must be saved so that
				 * if the currentItem is deleted, can pick
				 * another. */
    int state;			/* Last known modifier state. Used to defer
				 * picking a new current object while buttons
				 * are down. */

    /*
     * Information used for managing scrollbars:
     */

    char *xScrollCmd;		/* Command prefix for communicating with
				 * horizontal scrollbar. NULL means no
				 * horizontal scrollbar. Malloc'ed. */
    char *yScrollCmd;		/* Command prefix for communicating with
				 * vertical scrollbar. NULL means no vertical
				 * scrollbar. Malloc'ed. */
    int scrollX1, scrollY1, scrollX2, scrollY2;
				/* These four coordinates define the region
				 * that is the 100% area for scrolling (i.e.
				 * these numbers determine the size and
				 * location of the sliders on scrollbars).
				 * Units are pixels in canvas coords. */
    char *regionString;		/* The option string from which scrollX1 etc.
				 * are derived. Malloc'ed. */
    int xScrollIncrement;	/* If >0, defines a grid for horizontal
				 * scrolling. This is the size of the "unit",
				 * and the left edge of the screen will always
				 * lie on an even unit boundary. */
    int yScrollIncrement;	/* If >0, defines a grid for horizontal
				 * scrolling. This is the size of the "unit",
				 * and the left edge of the screen will always
				 * lie on an even unit boundary. */

    /*
     * Information used for scanning:
     */

    int scanX;			/* X-position at which scan started (e.g.
				 * button was pressed here). */
    int scanXOrigin;		/* Value of xOrigin field when scan started. */
    int scanY;			/* Y-position at which scan started (e.g.
				 * button was pressed here). */
    int scanYOrigin;		/* Value of yOrigin field when scan started. */

    /*
     * Information used to speed up searches by remembering the last item
     * created or found with an item id search.
     */

    Tk_Item *hotPtr;		/* Pointer to "hot" item (one that's been
				 * recently used. NULL means there's no hot
				 * item. */
    Tk_Item *hotPrevPtr;	/* Pointer to predecessor to hotPtr (NULL
				 * means item is first in list). This is only
				 * a hint and may not really be hotPtr's
				 * predecessor. */

    /*
     * Miscellaneous information:
     */

    Tk_Cursor cursor;		/* Current cursor for window, or NULL. */
    char *takeFocus;		/* Value of -takefocus option; not used in the
				 * C code, but used by keyboard traversal
				 * scripts. Malloc'ed, but may be NULL. */
    double pixelsPerMM;		/* Scale factor between MM and pixels; used
				 * when converting coordinates. */
    int flags;			/* Various flags; see below for
				 * definitions. */
    int nextId;			/* Number to use as id for next item created
				 * in widget. */
    Tk_PostscriptInfo psInfo;	/* Pointer to information used for generating
				 * Postscript for the canvas. NULL means no
				 * Postscript is currently being generated. */
    Tcl_HashTable idTable;	/* Table of integer indices. */

    /*
     * Additional information, added by the 'dash'-patch
     */

    void *reserved1;
    Tk_State canvas_state;	/* State of canvas. */
    void *reserved2;
    void *reserved3;
    Tk_TSOffset tsoffset;
#ifndef USE_OLD_TAG_SEARCH
    TagSearchExpr *bindTagExprs;/* Linked list of tag expressions used in
				 * bindings. */
#endif
} TkCanvas;

/*
 * Flag bits for canvases:
 *
 * REDRAW_PENDING -		1 means a DoWhenIdle handler has already been
 *				created to redraw some or all of the canvas.
 * REDRAW_BORDERS - 		1 means that the borders need to be redrawn
 *				during the next redisplay operation.
 * REPICK_NEEDED -		1 means DisplayCanvas should pick a new
 *				current item before redrawing the canvas.
 * GOT_FOCUS -			1 means the focus is currently in this widget,
 *				so should draw the insertion cursor and
 *				traversal highlight.
 * CURSOR_ON -			1 means the insertion cursor is in the "on"
 *				phase of its blink cycle. 0 means either we
 *				don't have the focus or the cursor is in the
 *				"off" phase of its cycle.
 * UPDATE_SCROLLBARS -		1 means the scrollbars should get updated as
 *				part of the next display operation.
 * LEFT_GRABBED_ITEM -		1 means that the mouse left the current item
 *				while a grab was in effect, so we didn't
 *				change canvasPtr->currentItemPtr.
 * REPICK_IN_PROGRESS -		1 means PickCurrentItem is currently
 *				executing. If it should be called recursively,
 *				it should simply return immediately.
 * BBOX_NOT_EMPTY -		1 means that the bounding box of the area that
 *				should be redrawn is not empty.
 */

#define REDRAW_PENDING		1
#define REDRAW_BORDERS		2
#define REPICK_NEEDED		4
#define GOT_FOCUS		8
#define CURSOR_ON		0x10
#define UPDATE_SCROLLBARS	0x20
#define LEFT_GRABBED_ITEM	0x40
#define REPICK_IN_PROGRESS	0x100
#define BBOX_NOT_EMPTY		0x200

/*
 * Flag bits for canvas items (redraw_flags):
 *
 * FORCE_REDRAW -		1 means that the new coordinates of some item
 *				are not yet registered using
 *				Tk_CanvasEventuallyRedraw(). It should still
 *				be done by the general canvas code.
 */

#define FORCE_REDRAW		8

/*
 * Canvas-related functions that are shared among Tk modules but not exported
 * to the outside world:
 */

MODULE_SCOPE int	TkCanvPostscriptCmd(TkCanvas *canvasPtr,
			    Tcl_Interp *interp, int argc, const char **argv);
MODULE_SCOPE int 	TkCanvTranslatePath(TkCanvas *canvPtr,
			    int numVertex, double *coordPtr, int closed,
			    XPoint *outPtr);
/*
 * Standard item types provided by Tk:
 */

MODULE_SCOPE Tk_ItemType tkArcType, tkBitmapType, tkImageType, tkLineType;
MODULE_SCOPE Tk_ItemType tkOvalType, tkPolygonType;
MODULE_SCOPE Tk_ItemType tkRectangleType, tkTextType, tkWindowType;

/*
 * Convenience macro.
 */

#define Canvas(canvas) ((TkCanvas *) (canvas))

#endif /* _TKCANVAS */
