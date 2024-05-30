/*
 * tkButton.h --
 *
 *	Declarations of types and functions used to implement button-like
 *	widgets.
 *
 * Copyright (c) 1996-1998 by Sun Microsystems, Inc.
 *
 * See the file "license.terms" for information on usage and redistribution of
 * this file, and for a DISCLAIMER OF ALL WARRANTIES.
 */

#ifndef _TKBUTTON
#define _TKBUTTON

#ifndef _TKINT
#include "tkInt.h"
#endif

/*
 * Legal values for the "compound" field of TkButton records.
 */

enum compound {
    COMPOUND_BOTTOM, COMPOUND_CENTER, COMPOUND_LEFT, COMPOUND_NONE,
	COMPOUND_RIGHT, COMPOUND_TOP
};

/*
 * Legal values for the "state" field of TkButton records.
 */

enum state {
    STATE_ACTIVE, STATE_DISABLED, STATE_NORMAL
};

/*
 * Legal values for the "defaultState" field of TkButton records.
 */

enum defaultState {
    DEFAULT_ACTIVE, DEFAULT_DISABLED, DEFAULT_NORMAL
};

/*
 * A data structure of the following type is kept for each widget managed by
 * this file:
 */

typedef struct {
    Tk_Window tkwin;		/* Window that embodies the button. NULL means
				 * that the window has been destroyed. */
    Display *display;		/* Display containing widget. Needed to free
				 * up resources after tkwin is gone. */
    Tcl_Interp *interp;		/* Interpreter associated with button. */
    Tcl_Command widgetCmd;	/* Token for button's widget command. */
    int type;			/* Type of widget, such as TYPE_LABEL:
				 * restricts operations that may be performed
				 * on widget. See below for legal values. */
    Tk_OptionTable optionTable;	/* Table that defines configuration options
				 * available for this widget. */

    /*
     * Information about what's in the button.
     */

    Tcl_Obj *textPtr;		/* Value of -text option: specifies text to
				 * display in button. */
    int underline;		/* Value of -underline option: specifies index
				 * of character to underline. < 0 means don't
				 * underline anything. */
    Tcl_Obj *textVarNamePtr;	/* Value of -textvariable option: specifies
				 * name of variable or NULL. If non-NULL,
				 * button displays the contents of this
				 * variable. */
    Pixmap bitmap;		/* Value of -bitmap option. If not None,
				 * specifies bitmap to display and text and
				 * textVar are ignored. */
    Tcl_Obj *imagePtr;		/* Value of -image option: specifies image to
				 * display in window, or NULL if none. If
				 * non-NULL, bitmap, text, and textVarName are
				 * ignored.*/
    Tk_Image image;		/* Derived from imagePtr by calling
				 * Tk_GetImage, or NULL if imagePtr is
				 * NULL. */
    Tcl_Obj *selectImagePtr;	/* Value of -selectimage option: specifies
				 * image to display in window when selected,
				 * or NULL if none. Ignored if imagePtr is
				 * NULL. */
    Tk_Image selectImage;	/* Derived from selectImagePtr by calling
				 * Tk_GetImage, or NULL if selectImagePtr is
				 * NULL. */
    Tcl_Obj *tristateImagePtr;	/* Value of -tristateimage option: specifies
				 * image to display in window when selected,
				 * or NULL if none. Ignored if imagePtr is
				 * NULL. */
    Tk_Image tristateImage;	/* Derived from tristateImagePtr by calling
				 * Tk_GetImage, or NULL if tristateImagePtr is
				 * NULL. */

    /*
     * Information used when displaying widget:
     */

    enum state state;		/* Value of -state option: specifies state of
				 * button for display purposes.*/
    Tk_3DBorder normalBorder;	/* Value of -background option: specifies
				 * color for background (and border) when
				 * window isn't active. */
    Tk_3DBorder activeBorder;	/* Value of -activebackground option: this is
				 * the color used to draw 3-D border and
				 * background when widget is active. */
    Tcl_Obj *borderWidthPtr;	/* Value of -borderWidth option: specifies
				 * width of border in pixels. */
    int borderWidth;		/* Integer value corresponding to
				 * borderWidthPtr. Always >= 0. */
    int relief;			/* Value of -relief option: specifies 3-d
				 * effect for border, such as
				 * TK_RELIEF_RAISED. */
    int overRelief;		/* Value of -overrelief option: specifies a
				 * 3-d effect for the border, such as
				 * TK_RELIEF_RAISED, to be used when the mouse
				 * is over the button. */
    int offRelief;		/* Value of -offrelief option: specifies a 3-d
				 * effect for the border, such as
				 * TK_RELIEF_RAISED, to be used when a
				 * checkbutton or radiobutton without
				 * indicator is off. */
    Tcl_Obj *highlightWidthPtr;	/* Value of -highlightthickness option:
				 * specifies width in pixels of highlight to
				 * draw around widget when it has the focus.
				 * <= 0 means don't draw a highlight. */
    int highlightWidth;		/* Integer value corresponding to
				 * highlightWidthPtr. Always >= 0. */
    Tk_3DBorder highlightBorder;/* Value of -highlightbackground option:
				 * specifies background with which to draw 3-D
				 * default ring and focus highlight area when
				 * highlight is off. */
    XColor *highlightColorPtr;	/* Value of -highlightcolor option: specifies
				 * color for drawing traversal highlight. */
    int inset;			/* Total width of all borders, including
				 * traversal highlight and 3-D border.
				 * Indicates how much interior stuff must be
				 * offset from outside edges to leave room for
				 * borders. */
    Tk_Font tkfont;		/* Value of -font option: specifies font to
				 * use for display text. */
    XColor *normalFg;		/* Value of -font option: specifies foreground
				 * color in normal mode. */
    XColor *activeFg;		/* Value of -activeforeground option:
				 * foreground color in active mode. NULL means
				 * use -foreground instead. */
    XColor *disabledFg;		/* Value of -disabledforeground option:
				 * foreground color when disabled. NULL means
				 * use normalFg with a 50% stipple instead. */
    GC normalTextGC;		/* GC for drawing text in normal mode. Also
				 * used to copy from off-screen pixmap onto
				 * screen. */
    GC activeTextGC;		/* GC for drawing text in active mode (NULL
				 * means use normalTextGC). */
    GC disabledGC;		/* Used to produce disabled effect for text
				 * and check/radio marks. */
    GC stippleGC;		/* Used to produce disabled stipple effect for
				 * images when disabled. */
    Pixmap gray;		/* Pixmap for displaying disabled text if
				 * disabledFg is NULL. */
    GC copyGC;			/* Used for copying information from an
				 * off-screen pixmap to the screen. */
    Tcl_Obj *widthPtr;		/* Value of -width option. */
    int width;			/* Integer value corresponding to widthPtr. */
    Tcl_Obj *heightPtr;		/* Value of -height option. */
    int height;			/* Integer value corresponding to heightPtr. */
    Tcl_Obj *wrapLengthPtr;	/* Value of -wraplength option: specifies line
				 * length (in pixels) at which to wrap onto
				 * next line. <= 0 means don't wrap except at
				 * newlines. */
    int wrapLength;		/* Integer value corresponding to
				 * wrapLengthPtr. */
    Tcl_Obj *padXPtr;		/* Value of -padx option: specifies how many
				 * pixels of extra space to leave on left and
				 * right of text. Ignored for bitmaps and
				 * images. */
    int padX;			/* Integer value corresponding to padXPtr. */
    Tcl_Obj *padYPtr;		/* Value of -padx option: specifies how many
				 * pixels of extra space to leave above and
				 * below text. Ignored for bitmaps and
				 * images. */
    int padY;			/* Integer value corresponding to padYPtr. */
    Tk_Anchor anchor;		/* Value of -anchor option: specifies where
				 * text/bitmap should be displayed inside
				 * button region. */
    Tk_Justify justify;		/* Value of -justify option: specifies how to
				 * align lines of multi-line text. */
    int indicatorOn;		/* Value of -indicatoron option: 1 means draw
				 * indicator in checkbuttons and radiobuttons,
				 * 0 means don't draw it. */
    Tk_3DBorder selectBorder;	/* Value of -selectcolor option: specifies
				 * color for drawing indicator background, or
				 * perhaps widget background, when
				 * selected. */
    int textWidth;		/* Width needed to display text as requested,
				 * in pixels. */
    int textHeight;		/* Height needed to display text as requested,
				 * in pixels. */
    Tk_TextLayout textLayout;	/* Saved text layout information. */
    int indicatorSpace;		/* Horizontal space (in pixels) allocated for
				 * display of indicator. */
    int indicatorDiameter;	/* Diameter of indicator, in pixels. */
    enum defaultState defaultState;
				/* Value of -default option, such as
				 * DEFAULT_NORMAL: specifies state of default
				 * ring for buttons (normal, active, or
				 * disabled). NULL for other classes. */

    /*
     * For check and radio buttons, the fields below are used to manage the
     * variable indicating the button's state.
     */

    Tcl_Obj *selVarNamePtr;	/* Value of -variable option: specifies name
				 * of variable used to control selected state
				 * of button. */
    Tcl_Obj *onValuePtr;	/* Value of -offvalue option: specifies value
				 * to store in variable when this button is
				 * selected. */
    Tcl_Obj *offValuePtr;	/* Value of -offvalue option: specifies value
				 * to store in variable when this button isn't
				 * selected. Used only by checkbuttons. */
    Tcl_Obj *tristateValuePtr;	/* Value of -tristatevalue option: specifies
				 * value to display Tristate or Multivalue
				 * mode when variable matches this value.
				 * Used by check- buttons. */

    /*
     * Miscellaneous information:
     */

    Tk_Cursor cursor;		/* Value of -cursor option: if not NULL,
				 * specifies current cursor for window. */
    Tcl_Obj *takeFocusPtr;	/* Value of -takefocus option; not used in the
				 * C code, but used by keyboard traversal
				 * scripts. */
    Tcl_Obj *commandPtr;	/* Value of -command option: specifies script
				 * to execute when button is invoked. If
				 * widget is label or has no command, this is
				 * NULL. */
    int compound;		/* Value of -compound option; specifies
				 * whether the button should show both an
				 * image and text, and, if so, how. */
    int repeatDelay;		/* Value of -repeatdelay option; specifies the
				 * number of ms after which the button will
				 * start to auto-repeat its command. */
    int repeatInterval;		/* Value of -repeatinterval option; specifies
				 * the number of ms between auto-repeat
				 * invocataions of the button command. */
    int flags;			/* Various flags; see below for
				 * definitions. */
} TkButton;

/*
 * Possible "type" values for buttons. These are the kinds of widgets
 * supported by this file. The ordering of the type numbers is significant:
 * greater means more features and is used in the code.
 */

#define TYPE_LABEL		0
#define TYPE_BUTTON		1
#define TYPE_CHECK_BUTTON	2
#define TYPE_RADIO_BUTTON	3

/*
 * Flag bits for buttons:
 *
 * REDRAW_PENDING:		Non-zero means a DoWhenIdle handler has
 *				already been queued to redraw this window.
 * SELECTED:			Non-zero means this button is selected, so
 *				special highlight should be drawn.
 * GOT_FOCUS:			Non-zero means this button currently has the
 *				input focus.
 * BUTTON_DELETED:		Non-zero needs that this button has been
 *				deleted, or is in the process of being deleted
 */

#define REDRAW_PENDING		(1 << 0)
#define SELECTED		(1 << 1)
#define GOT_FOCUS		(1 << 2)
#define BUTTON_DELETED		(1 << 3)
#define TRISTATED		(1 << 4)

/*
 * Declaration of button class functions structure
 * and button/label defaults, for use in optionSpecs.
 */

MODULE_SCOPE const Tk_ClassProcs tkpButtonProcs;
MODULE_SCOPE char tkDefButtonHighlightWidth[TCL_INTEGER_SPACE];
MODULE_SCOPE char tkDefButtonPadx[TCL_INTEGER_SPACE];
MODULE_SCOPE char tkDefButtonPady[TCL_INTEGER_SPACE];
MODULE_SCOPE char tkDefButtonBorderWidth[TCL_INTEGER_SPACE];
MODULE_SCOPE char tkDefLabelHighlightWidth[TCL_INTEGER_SPACE];
MODULE_SCOPE char tkDefLabelPadx[TCL_INTEGER_SPACE];
MODULE_SCOPE char tkDefLabelPady[TCL_INTEGER_SPACE];

/*
 * Declaration of functions used in the implementation of the button widget.
 */

#ifndef TkpButtonSetDefaults
MODULE_SCOPE void	TkpButtonSetDefaults(void);
#endif
MODULE_SCOPE void	TkButtonWorldChanged(ClientData instanceData);
MODULE_SCOPE void	TkpComputeButtonGeometry(TkButton *butPtr);
MODULE_SCOPE TkButton	*TkpCreateButton(Tk_Window tkwin);
#ifndef TkpDestroyButton
MODULE_SCOPE void 	TkpDestroyButton(TkButton *butPtr);
#endif
#ifndef TkpDisplayButton
MODULE_SCOPE void	TkpDisplayButton(ClientData clientData);
#endif
MODULE_SCOPE int	TkInvokeButton(TkButton *butPtr);

#endif /* _TKBUTTON */
