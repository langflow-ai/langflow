/*
 * tkScrollbar.h --
 *
 *	Declarations of types and functions used to implement the scrollbar
 *	widget.
 *
 * Copyright (c) 1996 by Sun Microsystems, Inc.
 *
 * See the file "license.terms" for information on usage and redistribution of
 * this file, and for a DISCLAIMER OF ALL WARRANTIES.
 */

#ifndef _TKSCROLLBAR
#define _TKSCROLLBAR

#ifndef _TKINT
#include "tkInt.h"
#endif

/*
 * A data structure of the following type is kept for each scrollbar widget.
 */

typedef struct TkScrollbar {
    Tk_Window tkwin;		/* Window that embodies the scrollbar. NULL
				 * means that the window has been destroyed
				 * but the data structures haven't yet been
				 * cleaned up.*/
    Display *display;		/* Display containing widget. Used, among
				 * other things, so that resources can be
				 * freed even after tkwin has gone away. */
    Tcl_Interp *interp;		/* Interpreter associated with scrollbar. */
    Tcl_Command widgetCmd;	/* Token for scrollbar's widget command. */
    int vertical;		/* Non-zero means vertical orientation
				 * requested, zero means horizontal. */
    int width;			/* Desired narrow dimension of scrollbar, in
				 * pixels. */
    char *command;		/* Command prefix to use when invoking
				 * scrolling commands. NULL means don't invoke
				 * commands. Malloc'ed. */
    int commandSize;		/* Number of non-NULL bytes in command. */
    int repeatDelay;		/* How long to wait before auto-repeating on
				 * scrolling actions (in ms). */
    int repeatInterval;		/* Interval between autorepeats (in ms). */
    int jump;			/* Value of -jump option. */

    /*
     * Information used when displaying widget:
     */

    int borderWidth;		/* Width of 3-D borders. */
    Tk_3DBorder bgBorder;	/* Used for drawing background (all flat
				 * surfaces except for trough). */
    Tk_3DBorder activeBorder;	/* For drawing backgrounds when active (i.e.
				 * when mouse is positioned over element). */
    XColor *troughColorPtr;	/* Color for drawing trough. */
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
    int elementBorderWidth;	/* Width of border to draw around elements
				 * inside scrollbar (arrows and slider). -1
				 * means use borderWidth. */
    int arrowLength;		/* Length of arrows along long dimension of
				 * scrollbar, including space for a small gap
				 * between the arrow and the slider.
				 * Recomputed on window size changes. */
    int sliderFirst;		/* Pixel coordinate of top or left edge of
				 * slider area, including border. */
    int sliderLast;		/* Coordinate of pixel just after bottom or
				 * right edge of slider area, including
				 * border. */
    int activeField;		/* Names field to be displayed in active
				 * colors, such as TOP_ARROW, or 0 for no
				 * field. */
    int activeRelief;		/* Value of -activeRelief option: relief to
				 * use for active element. */

    /*
     * Information describing the application related to the scrollbar. This
     * information is provided by the application by invoking the "set" widget
     * command. This information can now be provided in two ways: the "old"
     * form (totalUnits, windowUnits, firstUnit, and lastUnit), or the "new"
     * form (firstFraction and lastFraction). FirstFraction and lastFraction
     * will always be valid, but the old-style information is only valid if
     * the NEW_STYLE_COMMANDS flag is 0.
     */

    int totalUnits;		/* Total dimension of application, in units.
				 * Valid only if the NEW_STYLE_COMMANDS flag
				 * isn't set. */
    int windowUnits;		/* Maximum number of units that can be
				 * displayed in the window at once. Valid only
				 * if the NEW_STYLE_COMMANDS flag isn't set. */
    int firstUnit;		/* Number of last unit visible in
				 * application's window. Valid only if the
				 * NEW_STYLE_COMMANDS flag isn't set. */
    int lastUnit;		/* Index of last unit visible in window.
				 * Valid only if the NEW_STYLE_COMMANDS flag
				 * isn't set. */
    double firstFraction;	/* Position of first visible thing in window,
				 * specified as a fraction between 0 and
				 * 1.0. */
    double lastFraction;	/* Position of last visible thing in window,
				 * specified as a fraction between 0 and
				 * 1.0. */

    /*
     * Miscellaneous information:
     */

    Tk_Cursor cursor;		/* Current cursor for window, or NULL. */
    char *takeFocus;		/* Value of -takefocus option; not used in the
				 * C code, but used by keyboard traversal
				 * scripts. Malloc'ed, but may be NULL. */
    int flags;			/* Various flags; see below for
				 * definitions. */
} TkScrollbar;

/*
 * Legal values for "activeField" field of Scrollbar structures. These are
 * also the return values from the ScrollbarPosition function.
 */

#define OUTSIDE		0
#define TOP_ARROW	1
#define TOP_GAP		2
#define SLIDER		3
#define BOTTOM_GAP	4
#define BOTTOM_ARROW	5

/*
 * Flag bits for scrollbars:
 *
 * REDRAW_PENDING:		Non-zero means a DoWhenIdle handler has
 *				already been queued to redraw this window.
 * NEW_STYLE_COMMANDS:		Non-zero means the new style of commands
 *				should be used to communicate with the widget:
 *				".t yview scroll 2 lines", instead of
 *				".t yview 40", for example.
 * GOT_FOCUS:			Non-zero means this window has the input
 *				focus.
 */

#define REDRAW_PENDING		1
#define NEW_STYLE_COMMANDS	2
#define GOT_FOCUS		4

/*
 * Declaration of scrollbar class functions structure
 * and default scrollbar width, for use in configSpec.
 */

MODULE_SCOPE const Tk_ClassProcs tkpScrollbarProcs;
MODULE_SCOPE char tkDefScrollbarWidth[TCL_INTEGER_SPACE];

/*
 * Declaration of functions used in the implementation of the scrollbar
 * widget.
 */

MODULE_SCOPE void	TkScrollbarEventProc(ClientData clientData,
			    XEvent *eventPtr);
MODULE_SCOPE void	TkScrollbarEventuallyRedraw(TkScrollbar *scrollPtr);
MODULE_SCOPE void	TkpComputeScrollbarGeometry(TkScrollbar *scrollPtr);
MODULE_SCOPE TkScrollbar *TkpCreateScrollbar(Tk_Window tkwin);
MODULE_SCOPE void 	TkpDestroyScrollbar(TkScrollbar *scrollPtr);
MODULE_SCOPE void	TkpDisplayScrollbar(ClientData clientData);
MODULE_SCOPE void	TkpConfigureScrollbar(TkScrollbar *scrollPtr);
MODULE_SCOPE int	TkpScrollbarPosition(TkScrollbar *scrollPtr,
			    int x, int y);

#endif /* _TKSCROLLBAR */
