/*
 * tkScale.h --
 *
 *	Declarations of types and functions used to implement the scale
 *	widget.
 *
 * Copyright (c) 1996 by Sun Microsystems, Inc.
 * Copyright (c) 1999-2000 by Scriptics Corporation.
 *
 * See the file "license.terms" for information on usage and redistribution of
 * this file, and for a DISCLAIMER OF ALL WARRANTIES.
 */

#ifndef _TKSCALE
#define _TKSCALE

#ifndef _TKINT
#include "tkInt.h"
#endif

/*
 * Legal values for the "orient" field of TkScale records.
 */

enum orient {
    ORIENT_HORIZONTAL, ORIENT_VERTICAL
};

/*
 * Legal values for the "state" field of TkScale records.
 */

enum state {
    STATE_ACTIVE, STATE_DISABLED, STATE_NORMAL
};

/*
 * A data structure of the following type is kept for each scale widget
 * managed by this file:
 */

typedef struct TkScale {
    Tk_Window tkwin;		/* Window that embodies the scale. NULL means
				 * that the window has been destroyed but the
				 * data structures haven't yet been cleaned
				 * up.*/
    Display *display;		/* Display containing widget. Used, among
				 * other things, so that resources can be
				 * freed even after tkwin has gone away. */
    Tcl_Interp *interp;		/* Interpreter associated with scale. */
    Tcl_Command widgetCmd;	/* Token for scale's widget command. */
    Tk_OptionTable optionTable;	/* Table that defines configuration options
				 * available for this widget. */
    enum orient orient;		/* Orientation for window (vertical or
				 * horizontal). */
    int width;			/* Desired narrow dimension of scale, in
				 * pixels. */
    int length;			/* Desired long dimension of scale, in
				 * pixels. */
    double value;		/* Current value of scale. */
    Tcl_Obj *varNamePtr;	/* Name of variable or NULL. If non-NULL,
				 * scale's value tracks the contents of this
				 * variable and vice versa. */
    double fromValue;		/* Value corresponding to left or top of
				 * scale. */
    double toValue;		/* Value corresponding to right or bottom of
				 * scale. */
    double tickInterval;	/* Distance between tick marks; 0 means don't
				 * display any tick marks. */
    double resolution;		/* If > 0, all values are rounded to an even
				 * multiple of this value. */
    int digits;			/* Number of significant digits to print in
				 * values. 0 means we get to choose the number
				 * based on resolution and/or the range of the
				 * scale. */
    char valueFormat[16];	/* Snprintf conversion specifier computed from
				 * digits and other information. */
    char tickFormat[16];	/* Snprintf conversion specifier computed from
				 * tick interval. */
    double bigIncrement;	/* Amount to use for large increments to scale
				 * value. (0 means we pick a value). */
    char *command;		/* Command prefix to use when invoking Tcl
				 * commands because the scale value changed.
				 * NULL means don't invoke commands. */
    int repeatDelay;		/* How long to wait before auto-repeating on
				 * scrolling actions (in ms). */
    int repeatInterval;		/* Interval between autorepeats (in ms). */
    char *label;		/* Label to display above or to right of
				 * scale; NULL means don't display a label. */
    int labelLength;		/* Number of non-NULL chars. in label. */
    enum state state;		/* Values are active, normal, or disabled.
				 * Value of scale cannot be changed when
				 * disabled. */

    /*
     * Information used when displaying widget:
     */

    int borderWidth;		/* Width of 3-D border around window. */
    Tk_3DBorder bgBorder;	/* Used for drawing slider and other
				 * background areas. */
    Tk_3DBorder activeBorder;	/* For drawing the slider when active. */
    int sliderRelief;		/* Is slider to be drawn raised, sunken,
				 * etc. */
    XColor *troughColorPtr;	/* Color for drawing trough. */
    GC troughGC;		/* For drawing trough. */
    GC copyGC;			/* Used for copying from pixmap onto screen */
    Tk_Font tkfont;		/* Information about text font, or NULL. */
    XColor *textColorPtr;	/* Color for drawing text. */
    GC textGC;			/* GC for drawing text in normal mode. */
    int relief;			/* Indicates whether window as a whole is
				 * raised, sunken, or flat. */
    int highlightWidth;		/* Width in pixels of highlight to draw around
				 * widget when it has the focus. <= 0 means
				 * don't draw a highlight. */
    Tk_3DBorder highlightBorder;/* Value of -highlightbackground option:
				 * specifies background with which to draw 3-D
				 * default ring and focus highlight area when
				 * highlight is off. */
    XColor *highlightColorPtr;	/* Color for drawing traversal highlight. */
    int inset;			/* Total width of all borders, including
				 * traversal highlight and 3-D border.
				 * Indicates how much interior stuff must be
				 * offset from outside edges to leave room for
				 * borders. */
    int sliderLength;		/* Length of slider, measured in pixels along
				 * long dimension of scale. */
    int showValue;		/* Non-zero means to display the scale value
				 * below or to the left of the slider; zero
				 * means don't display the value. */

    /*
     * Layout information for horizontal scales, assuming that window gets the
     * size it requested:
     */

    int horizLabelY;		/* Y-coord at which to draw label. */
    int horizValueY;		/* Y-coord at which to draw value text. */
    int horizTroughY;		/* Y-coord of top of slider trough. */
    int horizTickY;		/* Y-coord at which to draw tick text. */
    /*
     * Layout information for vertical scales, assuming that window gets the
     * size it requested:
     */

    int vertTickRightX;		/* X-location of right side of tick-marks. */
    int vertValueRightX;	/* X-location of right side of value string. */
    int vertTroughX;		/* X-location of scale's slider trough. */
    int vertLabelX;		/* X-location of origin of label. */

    /*
     * Miscellaneous information:
     */

    int fontHeight;		/* Height of scale font. */
    Tk_Cursor cursor;		/* Current cursor for window, or NULL. */
    Tcl_Obj *takeFocusPtr;	/* Value of -takefocus option; not used in the
				 * C code, but used by keyboard traversal
				 * scripts. May be NULL. */
    int flags;			/* Various flags; see below for
				 * definitions. */
} TkScale;

/*
 * Flag bits for scales:
 *
 * REDRAW_SLIDER -		1 means slider (and numerical readout) need to
 *				be redrawn.
 * REDRAW_OTHER -		1 means other stuff besides slider and value
 *				need to be redrawn.
 * REDRAW_ALL -			1 means the entire widget needs to be redrawn.
 * REDRAW_PENDING -		1 means any sort of redraw is pending
 * ACTIVE -			1 means the widget is active (the mouse is in
 *				its window).
 * INVOKE_COMMAND -		1 means the scale's command needs to be
 *				invoked during the next redisplay (the value
 *				of the scale has changed since the last time
 *				the command was invoked).
 * SETTING_VAR -		1 means that the associated variable is being
 *				set by us, so there's no need for ScaleVarProc
 *				to do anything.
 * NEVER_SET -			1 means that the scale's value has never been
 *				set before (so must invoke -command and set
 *				associated variable even if the value doesn't
 *				appear to have changed).
 * GOT_FOCUS -			1 means that the focus is currently in this
 *				widget.
 * SCALE_DELETED -		1 means the scale widget is being deleted
 */

#define REDRAW_SLIDER		(1<<0)
#define REDRAW_OTHER		(1<<1)
#define REDRAW_ALL		(REDRAW_OTHER|REDRAW_SLIDER)
#define REDRAW_PENDING		(1<<2)
#define ACTIVE			(1<<3)
#define INVOKE_COMMAND		(1<<4)
#define SETTING_VAR		(1<<5)
#define NEVER_SET		(1<<6)
#define GOT_FOCUS		(1<<7)
#define SCALE_DELETED		(1<<8)

/*
 * Symbolic values for the active parts of a slider. These are the values that
 * may be returned by the ScaleElement procedure.
 */

#define OTHER		0
#define TROUGH1		1
#define SLIDER		2
#define TROUGH2		3

/*
 * Space to leave between scale area and text, and between text and edge of
 * window.
 */

#define SPACING 2

/*
 * The tick values are all displayed with the same number of decimal places.
 * This number of decimal places is such that the displayed values are all
 * accurate to within the following proportion of a tick interval.
 */

#define TICK_VALUES_DISPLAY_ACCURACY 0.2

/*
 * Declaration of procedures used in the implementation of the scale widget.
 */

MODULE_SCOPE void	TkEventuallyRedrawScale(TkScale *scalePtr, int what);
MODULE_SCOPE double	TkRoundValueToResolution(TkScale *scalePtr, double value);
MODULE_SCOPE double	TkRoundIntervalToResolution(TkScale *scalePtr, double value);
MODULE_SCOPE TkScale *	TkpCreateScale(Tk_Window tkwin);
MODULE_SCOPE void	TkpDestroyScale(TkScale *scalePtr);
MODULE_SCOPE void	TkpDisplayScale(ClientData clientData);
MODULE_SCOPE int	TkpScaleElement(TkScale *scalePtr, int x, int y);
MODULE_SCOPE void	TkScaleSetValue(TkScale *scalePtr, double value,
			    int setVar, int invokeCommand);
MODULE_SCOPE double	TkScalePixelToValue(TkScale *scalePtr, int x, int y);
MODULE_SCOPE int	TkScaleValueToPixel(TkScale *scalePtr, double value);

#endif /* _TKSCALE */
