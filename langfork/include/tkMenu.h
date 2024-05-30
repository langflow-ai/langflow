/*
 * tkMenu.h --
 *
 *	Declarations shared among all of the files that implement menu
 *	widgets.
 *
 * Copyright (c) 1996-1998 by Sun Microsystems, Inc.
 *
 * See the file "license.terms" for information on usage and redistribution of
 * this file, and for a DISCLAIMER OF ALL WARRANTIES.
 */

#ifndef _TKMENU
#define _TKMENU

#ifndef _TKINT
#include "tkInt.h"
#endif

#ifndef _DEFAULT
#include "default.h"
#endif

/*
 * Dummy types used by the platform menu code.
 */

typedef struct TkMenuPlatformData_ *TkMenuPlatformData;
typedef struct TkMenuPlatformEntryData_ *TkMenuPlatformEntryData;

/*
 * Legal values for the "compound" field of TkMenuEntry and TkMenuButton
 * records.
 */

enum compound {
    COMPOUND_BOTTOM, COMPOUND_CENTER, COMPOUND_LEFT, COMPOUND_NONE,
    COMPOUND_RIGHT, COMPOUND_TOP
};

/*
 * Additional menu entry drawing parameters for Windows platform.
 * DRAW_MENU_ENTRY_ARROW makes TkpDrawMenuEntry draw the arrow
 * itself when cascade entry is disabled.
 * DRAW_MENU_ENTRY_NOUNDERLINE forbids underline when ODS_NOACCEL
 * is set, thus obeying the system-wide Windows UI setting.
 */

enum drawingParameters {
    DRAW_MENU_ENTRY_ARROW = (1<<0),
    DRAW_MENU_ENTRY_NOUNDERLINE = (1<<1)
};

/*
 * One of the following data structures is kept for each entry of each menu
 * managed by this file:
 */

typedef struct TkMenuEntry {
    int type;			/* Type of menu entry; see below for valid
				 * types. */
    struct TkMenu *menuPtr;	/* Menu with which this entry is
				 * associated. */
    Tk_OptionTable optionTable;	/* Option table for this menu entry. */
    Tcl_Obj *labelPtr;		/* Main text label displayed in entry (NULL if
				 * no label). */
    int labelLength;		/* Number of non-NULL characters in label. */
    int state;			/* State of button for display purposes:
				 * normal, active, or disabled. */
    int underline;		/* Value of -underline option: specifies index
				 * of character to underline (<0 means don't
				 * underline anything). */
    Tcl_Obj *underlinePtr;	/* Index of character to underline. */
    Tcl_Obj *bitmapPtr;		/* Bitmap to display in menu entry, or NULL.
				 * If not NULL then label is ignored. */
    Tcl_Obj *imagePtr;		/* Name of image to display, or NULL. If not
				 * NULL, bitmap, text, and textVarName are
				 * ignored. */
    Tk_Image image;		/* Image to display in menu entry, or NULL if
				 * none. */
    Tcl_Obj *selectImagePtr;	/* Name of image to display when selected, or
				 * NULL. */
    Tk_Image selectImage;	/* Image to display in entry when selected, or
				 * NULL if none. Ignored if image is NULL. */
    Tcl_Obj *accelPtr;		/* Accelerator string displayed at right of
				 * menu entry. NULL means no such accelerator.
				 * Malloc'ed. */
    int accelLength;		/* Number of non-NULL characters in
				 * accelerator. */
    int indicatorOn;		/* True means draw indicator, false means
				 * don't draw it. This field is ignored unless
				 * the entry is a radio or check button. */
    /*
     * Display attributes
     */

    Tcl_Obj *borderPtr;		/* Structure used to draw background for
				 * entry. NULL means use overall border for
				 * menu. */
    Tcl_Obj *fgPtr;		/* Foreground color to use for entry. NULL
				 * means use foreground color from menu. */
    Tcl_Obj *activeBorderPtr;	/* Used to draw background and border when
				 * element is active. NULL means use
				 * activeBorder from menu. */
    Tcl_Obj *activeFgPtr;	/* Foreground color to use when entry is
				 * active. NULL means use active foreground
				 * from menu. */
    Tcl_Obj *indicatorFgPtr;	/* Color for indicators in radio and check
				 * button entries. NULL means use indicatorFg
				 * GC from menu. */
    Tcl_Obj *fontPtr;		/* Text font for menu entries. NULL means use
				 * overall font for menu. */
    int columnBreak;		/* If this is 0, this item appears below the
				 * item in front of it. If this is 1, this
				 * item starts a new column. This field is
				 * always 0 for tearoff and separator
				 * entries. */
    int hideMargin;		/* If this is 0, then the item has enough
    				 * margin to accommodate a standard check mark
    				 * and a default right margin. If this is 1,
    				 * then the item has no such margins, and
    				 * checkbuttons and radiobuttons with this set
    				 * will have a rectangle drawn in the
    				 * indicator around the item if the item is
    				 * checked. This is useful for palette menus.
    				 * This field is ignored for separators and
    				 * tearoffs. */
    int indicatorSpace;		/* The width of the indicator space for this
				 * entry. */
    int labelWidth;		/* Number of pixels to allow for displaying
				 * labels in menu entries. */
    int compound;		/* Value of -compound option; specifies
				 * whether the entry should show both an image
				 * and text, and, if so, how. */

    /*
     * Information used to implement this entry's action:
     */

    Tcl_Obj *commandPtr;	/* Command to invoke when entry is invoked.
				 * Malloc'ed. */
    Tcl_Obj *namePtr;		/* Name of variable (for check buttons and
				 * radio buttons) or menu (for cascade
				 * entries). Malloc'ed. */
    Tcl_Obj *onValuePtr;	/* Value to store in variable when selected
				 * (only for radio and check buttons).
				 * Malloc'ed. */
    Tcl_Obj *offValuePtr;	/* Value to store in variable when not
				 * selected (only for check buttons).
				 * Malloc'ed. */

    /*
     * Information used for drawing this menu entry.
     */

    int width;			/* Number of pixels occupied by entry in
				 * horizontal dimension. Not used except in
				 * menubars. The width of norma menus is
				 * dependent on the rest of the menu. */
    int x;			/* X-coordinate of leftmost pixel in entry. */
    int height;			/* Number of pixels occupied by entry in
				 * vertical dimension, including raised border
				 * drawn around entry when active. */
    int y;			/* Y-coordinate of topmost pixel in entry. */
    GC textGC;			/* GC for drawing text in entry. NULL means
				 * use overall textGC for menu. */
    GC activeGC;		/* GC for drawing text in entry when active.
				 * NULL means use overall activeGC for
				 * menu. */
    GC disabledGC;		/* Used to produce disabled effect for entry.
				 * NULL means use overall disabledGC from menu
				 * structure. See comments for disabledFg in
				 * menu structure for more information. */
    GC indicatorGC;		/* For drawing indicators. NULL means use GC
				 * from menu. */

    /*
     * Miscellaneous fields.
     */

    int entryFlags;		/* Various flags. See below for
				 * definitions. */
    int index;			/* Need to know which index we are. This is
    				 * zero-based. This is the top-left entry of
    				 * the menu. */

    /*
     * Bookeeping for main menus and cascade menus.
     */

    struct TkMenuReferences *childMenuRefPtr;
    				/* A pointer to the hash table entry for the
    				 * child menu. Stored here when the menu entry
    				 * is configured so that a hash lookup is not
    				 * necessary later.*/
    struct TkMenuEntry *nextCascadePtr;
    				/* The next cascade entry that is a parent of
    				 * this entry's child cascade menu. NULL end
    				 * of list, this is not a cascade entry, or
    				 * the menu that this entry point to does not
    				 * yet exist. */
    TkMenuPlatformEntryData platformEntryData;
    				/* The data for the specific type of menu.
				 * Depends on platform and menu type what kind
				 * of options are in this structure. */
} TkMenuEntry;

/*
 * Flag values defined for menu entries:
 *
 * ENTRY_SELECTED:		Non-zero means this is a radio or check button
 *				and that it should be drawn in the "selected"
 *				state.
 * ENTRY_NEEDS_REDISPLAY:	Non-zero means the entry should be redisplayed.
 * ENTRY_LAST_COLUMN:		Used by the drawing code. If the entry is in
 *				the last column, the space to its right needs
 *				to be filled.
 * ENTRY_PLATFORM_FLAG1 - 4	These flags are reserved for use by the
 *				platform-dependent implementation of menus
 *				and should not be used by anything else.
 */

#define ENTRY_SELECTED		1
#define ENTRY_NEEDS_REDISPLAY	2
#define ENTRY_LAST_COLUMN	4
#define ENTRY_PLATFORM_FLAG1	(1 << 30)
#define ENTRY_PLATFORM_FLAG2	(1 << 29)
#define ENTRY_PLATFORM_FLAG3	(1 << 28)
#define ENTRY_PLATFORM_FLAG4	(1 << 27)

/*
 * Types defined for MenuEntries:
 */

#define CASCADE_ENTRY 0
#define CHECK_BUTTON_ENTRY 1
#define COMMAND_ENTRY 2
#define RADIO_BUTTON_ENTRY 3
#define SEPARATOR_ENTRY 4
#define TEAROFF_ENTRY 5

/*
 * Menu states
 */

#define ENTRY_ACTIVE 0
#define ENTRY_NORMAL 1
#define ENTRY_DISABLED 2

/*
 * A data structure of the following type is kept for each menu widget:
 */

typedef struct TkMenu {
    Tk_Window tkwin;		/* Window that embodies the pane. NULL means
				 * that the window has been destroyed but the
				 * data structures haven't yet been cleaned
				 * up. */
    Display *display;		/* Display containing widget. Needed, among
				 * other things, so that resources can be
				 * freed up even after tkwin has gone away. */
    Tcl_Interp *interp;		/* Interpreter associated with menu. */
    Tcl_Command widgetCmd;	/* Token for menu's widget command. */
    TkMenuEntry **entries;	/* Array of pointers to all the entries in the
				 * menu. NULL means no entries. */
    int numEntries;		/* Number of elements in entries. */
    int active;			/* Index of active entry. -1 means nothing
				 * active. */
    int menuType;		/* MAIN_MENU, TEAROFF_MENU, or MENUBAR. See
    				 * below for definitions. */
    Tcl_Obj *menuTypePtr;	/* Used to control whether created tkwin is a
				 * toplevel or not. "normal", "menubar", or
				 * "toplevel" */

    /*
     * Information used when displaying widget:
     */

    Tcl_Obj *borderPtr;		/* Structure used to draw 3-D border and
				 * background for menu. */
    Tcl_Obj *borderWidthPtr;	/* Width of border around whole menu. */
    Tcl_Obj *activeBorderPtr;	/* Used to draw background and border for
				 * active element (if any). */
    Tcl_Obj *activeBorderWidthPtr;
				/* Width of border around active element. */
    Tcl_Obj *reliefPtr;		/* 3-d effect: TK_RELIEF_RAISED, etc. */
    Tcl_Obj *fontPtr;		/* Text font for menu entries. */
    Tcl_Obj *fgPtr;		/* Foreground color for entries. */
    Tcl_Obj *disabledFgPtr;	/* Foreground color when disabled. NULL means
				 * use normalFg with a 50% stipple instead. */
    Tcl_Obj *activeFgPtr;	/* Foreground color for active entry. */
    Tcl_Obj *indicatorFgPtr;	/* Color for indicators in radio and check
				 * button entries. */
    Pixmap gray;		/* Bitmap for drawing disabled entries in a
				 * stippled fashion. None means not allocated
				 * yet. */
    GC textGC;			/* GC for drawing text and other features of
				 * menu entries. */
    GC disabledGC;		/* Used to produce disabled effect. If
				 * disabledFg isn't NULL, this GC is used to
				 * draw text and icons for disabled entries.
				 * Otherwise text and icons are drawn with
				 * normalGC and this GC is used to stipple
				 * background across them. */
    GC activeGC;		/* GC for drawing active entry. */
    GC indicatorGC;		/* For drawing indicators. */
    GC disabledImageGC;		/* Used for drawing disabled images. They have
				 * to be stippled. This is created when the
				 * image is about to be drawn the first
				 * time. */

    /*
     * Information about geometry of menu.
     */

    int totalWidth;		/* Width of entire menu. */
    int totalHeight;		/* Height of entire menu. */

    /*
     * Miscellaneous information:
     */

    int tearoff;		/* 1 means this menu can be torn off. On some
    				 * platforms, the user can drag an outline of
    				 * the menu by just dragging outside of the
    				 * menu, and the tearoff is created where the
    				 * mouse is released. On others, an indicator
    				 * (such as a dashed stripe) is drawn, and
    				 * when the menu is selected, the tearoff is
    				 * created. */
    Tcl_Obj *titlePtr;		/* The title to use when this menu is torn
    				 * off. If this is NULL, a default scheme will
    				 * be used to generate a title for tearoff. */
    Tcl_Obj *tearoffCommandPtr;	/* If non-NULL, points to a command to run
				 * whenever the menu is torn-off. */
    Tcl_Obj *takeFocusPtr;	/* Value of -takefocus option; not used in the
				 * C code, but used by keyboard traversal
				 * scripts. Malloc'ed, but may be NULL. */
    Tcl_Obj *cursorPtr;		/* Current cursor for window, or NULL. */
    Tcl_Obj *postCommandPtr;	/* Used to detect cycles in cascade hierarchy
    				 * trees when preprocessing postcommands on
    				 * some platforms. See PostMenu for more
    				 * details. */
    int postCommandGeneration;	/* Need to do pre-invocation post command
				 * traversal. */
    int menuFlags;		/* Flags for use by X; see below for
				 * definition. */
    TkMenuEntry *postedCascade;	/* Points to menu entry for cascaded submenu
				 * that is currently posted or NULL if no
				 * submenu posted. */
    struct TkMenu *nextInstancePtr;
    				/* The next instance of this menu in the
    				 * chain. */
    struct TkMenu *masterMenuPtr;
    				/* A pointer to the original menu for this
    				 * clone chain. Points back to this structure
    				 * if this menu is a main menu. */
    void *reserved1; /* not used any more. */
    Tk_Window parentTopLevelPtr;/* If this menu is a menubar, this is the
    				 * toplevel that owns the menu. Only
    				 * applicable for menubar clones. */
    struct TkMenuReferences *menuRefPtr;
    				/* Each menu is hashed into a table with the
    				 * name of the menu's window as the key. The
    				 * information in this hash table includes a
    				 * pointer to the menu (so that cascades can
    				 * find this menu), a pointer to the list of
    				 * toplevel widgets that have this menu as its
    				 * menubar, and a list of menu entries that
    				 * have this menu specified as a cascade. */
    TkMenuPlatformData platformData;
				/* The data for the specific type of menu.
				 * Depends on platform and menu type what kind
				 * of options are in this structure. */
    Tk_OptionSpec *extensionPtr;/* Needed by the configuration package for
				 * this widget to be extended. */
    Tk_SavedOptions *errorStructPtr;
				/* We actually have to allocate these because
				 * multiple menus get changed during one
				 * ConfigureMenu call. */
} TkMenu;

/*
 * When the toplevel configure -menu command is executed, the menu may not
 * exist yet. We need to keep a linked list of windows that reference a
 * particular menu.
 */

typedef struct TkMenuTopLevelList {
    struct TkMenuTopLevelList *nextPtr;
    				/* The next window in the list. */
    Tk_Window tkwin;		/* The window that has this menu as its
				 * menubar. */
} TkMenuTopLevelList;

/*
 * The following structure is used to keep track of things which reference a
 * menu. It is created when:
 * - a menu is created.
 * - a cascade entry is added to a menu with a non-null name
 * - the "-menu" configuration option is used on a toplevel widget with a
 *   non-null parameter.
 *
 * One of these three fields must be non-NULL, but any of the fields may be
 * NULL. This structure makes it easy to determine whether or not anything
 * like recalculating platform data or geometry is necessary when one of the
 * three actions above is performed.
 */

typedef struct TkMenuReferences {
    struct TkMenu *menuPtr;	/* The menu data structure. This is NULL if
    				 * the menu does not exist. */
    TkMenuTopLevelList *topLevelListPtr;
    				/* First in the list of all toplevels that
    				 * have this menu as its menubar. NULL if no
    				 * toplevel widgets have this menu as its
    				 * menubar. */
    TkMenuEntry *parentEntryPtr;/* First in the list of all cascade menu
    				 * entries that have this menu as their child.
    				 * NULL means no cascade entries. */
    Tcl_HashEntry *hashEntryPtr;/* This is needed because the pathname of the
    				 * window (which is what we hash on) may not
    				 * be around when we are deleting. */
} TkMenuReferences;

/*
 * Flag bits for menus:
 *
 * REDRAW_PENDING:		Non-zero means a DoWhenIdle handler has
 *				already been queued to redraw this window.
 * RESIZE_PENDING:		Non-zero means a call to ComputeMenuGeometry
 *				has already been scheduled.
 * MENU_DELETION_PENDING	Non-zero means that we are currently
 *				destroying this menu's internal structures.
 *				This is useful when we are in the middle of
 *				cleaning this main menu's chain of menus up
 *				when TkDestroyMenu was called again on this
 *				menu (via a destroy binding or somesuch).
 * MENU_WIN_DESTRUCTION_PENDING Non-zero means we are in the middle of
 *				destroying this menu's Tk_Window.
 * MENU_PLATFORM_FLAG1...	Reserved for use by the platform-specific menu
 *				code.
 */

#define REDRAW_PENDING			1
#define RESIZE_PENDING			2
#define MENU_DELETION_PENDING		4
#define MENU_WIN_DESTRUCTION_PENDING	8
#define MENU_PLATFORM_FLAG1	(1 << 30)
#define MENU_PLATFORM_FLAG2	(1 << 29)
#define MENU_PLATFORM_FLAG3	(1 << 28)

/*
 * Each menu created by the user is a MAIN_MENU. When a menu is torn off, a
 * TEAROFF_MENU instance is created. When a menu is assigned to a toplevel as
 * a menu bar, a MENUBAR instance is created. All instances have the same
 * configuration information. If the main instance is deleted, all instances
 * are deleted. If one of the other instances is deleted, only that instance
 * is deleted.
 */

#define UNKNOWN_TYPE		-1
#define MAIN_MENU 		0
#define MASTER_MENU 		0
#define TEAROFF_MENU 		1
#define MENUBAR 		2

/*
 * Various geometry definitions:
 */

#define CASCADE_ARROW_HEIGHT	10
#define CASCADE_ARROW_WIDTH	8
#define DECORATION_BORDER_WIDTH	2

/*
 * Menu-related functions that are shared among Tk modules but not exported to
 * the outside world:
 */

MODULE_SCOPE int	TkActivateMenuEntry(TkMenu *menuPtr, int index);
MODULE_SCOPE void	TkBindMenu(Tk_Window tkwin, TkMenu *menuPtr);
MODULE_SCOPE TkMenuReferences*TkCreateMenuReferences(Tcl_Interp *interp,
			    const char *name);
MODULE_SCOPE void	TkDestroyMenu(TkMenu *menuPtr);
MODULE_SCOPE void	TkEventuallyRecomputeMenu(TkMenu *menuPtr);
MODULE_SCOPE void	TkEventuallyRedrawMenu(TkMenu *menuPtr,
			    TkMenuEntry *mePtr);
MODULE_SCOPE TkMenuReferences*TkFindMenuReferences(Tcl_Interp *interp, const char *name);
MODULE_SCOPE TkMenuReferences*TkFindMenuReferencesObj(Tcl_Interp *interp,
			    Tcl_Obj *namePtr);
MODULE_SCOPE int	TkFreeMenuReferences(TkMenuReferences *menuRefPtr);
MODULE_SCOPE Tcl_HashTable *TkGetMenuHashTable(Tcl_Interp *interp);
MODULE_SCOPE int	TkGetMenuIndex(Tcl_Interp *interp, TkMenu *menuPtr,
			    Tcl_Obj *objPtr, int lastOK, int *indexPtr);
MODULE_SCOPE void	TkMenuInitializeDrawingFields(TkMenu *menuPtr);
MODULE_SCOPE void	TkMenuInitializeEntryDrawingFields(TkMenuEntry *mePtr);
MODULE_SCOPE int	TkInvokeMenu(Tcl_Interp *interp, TkMenu *menuPtr,
			    int index);
MODULE_SCOPE void	TkMenuConfigureDrawOptions(TkMenu *menuPtr);
MODULE_SCOPE int	TkMenuConfigureEntryDrawOptions(
			    TkMenuEntry *mePtr, int index);
MODULE_SCOPE void	TkMenuFreeDrawOptions(TkMenu *menuPtr);
MODULE_SCOPE void	TkMenuEntryFreeDrawOptions(TkMenuEntry *mePtr);
MODULE_SCOPE void	TkMenuEventProc(ClientData clientData,
    			    XEvent *eventPtr);
MODULE_SCOPE void	TkMenuImageProc(ClientData clientData, int x, int y,
			    int width, int height, int imgWidth,
			    int imgHeight);
MODULE_SCOPE void	TkMenuInit(void);
MODULE_SCOPE void	TkMenuSelectImageProc(ClientData clientData, int x,
			    int y, int width, int height, int imgWidth,
			    int imgHeight);
MODULE_SCOPE Tcl_Obj *	TkNewMenuName(Tcl_Interp *interp,
			    Tcl_Obj *parentNamePtr, TkMenu *menuPtr);
MODULE_SCOPE int	TkPostCommand(TkMenu *menuPtr);
MODULE_SCOPE int	TkPostSubmenu(Tcl_Interp *interp, TkMenu *menuPtr,
			    TkMenuEntry *mePtr);
MODULE_SCOPE int	TkPostTearoffMenu(Tcl_Interp *interp, TkMenu *menuPtr,
			    int x, int y);
MODULE_SCOPE int	TkPreprocessMenu(TkMenu *menuPtr);
MODULE_SCOPE void	TkRecomputeMenu(TkMenu *menuPtr);

/*
 * These routines are the platform-dependent routines called by the common
 * code.
 */

MODULE_SCOPE void	TkpComputeMenubarGeometry(TkMenu *menuPtr);
MODULE_SCOPE void	TkpComputeStandardMenuGeometry(TkMenu *menuPtr);
MODULE_SCOPE int	TkpConfigureMenuEntry(TkMenuEntry *mePtr);
MODULE_SCOPE void	TkpDestroyMenu(TkMenu *menuPtr);
MODULE_SCOPE void	TkpDestroyMenuEntry(TkMenuEntry *mEntryPtr);
MODULE_SCOPE void	TkpDrawMenuEntry(TkMenuEntry *mePtr,
			    Drawable d, Tk_Font tkfont,
			    const Tk_FontMetrics *menuMetricsPtr, int x,
			    int y, int width, int height, int strictMotif,
			    int drawingParameters);
MODULE_SCOPE void	TkpMenuInit(void);
MODULE_SCOPE int	TkpMenuNewEntry(TkMenuEntry *mePtr);
MODULE_SCOPE int	TkpNewMenu(TkMenu *menuPtr);
MODULE_SCOPE int	TkpPostMenu(Tcl_Interp *interp, TkMenu *menuPtr,
			    int x, int y, int index);
MODULE_SCOPE int	TkpPostTearoffMenu(Tcl_Interp *interp, TkMenu *menuPtr,
			    int x, int y, int index);
MODULE_SCOPE void	TkpSetWindowMenuBar(Tk_Window tkwin, TkMenu *menuPtr);

#endif /* _TKMENU */
