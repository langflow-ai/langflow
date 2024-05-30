/*
 * tkMacOSXPrivate.h --
 *
 *	Macros and declarations that are purely internal & private to TkAqua.
 *
 * Copyright (c) 2005-2009 Daniel A. Steffen <das@users.sourceforge.net>
 * Copyright (c) 2008-2009 Apple Inc.
 * Copyright (c) 2020 Marc Culler
 *
 * See the file "license.terms" for information on usage and redistribution
 * of this file, and for a DISCLAIMER OF ALL WARRANTIES.
 *
 * RCS: @(#) $Id$
 */

#ifndef _TKMACPRIV
#define _TKMACPRIV

#if !__OBJC__
#error Objective-C compiler required
#endif

#ifndef __clang__
#define instancetype id
#endif

#define TextStyle MacTextStyle
#import <ApplicationServices/ApplicationServices.h>
#import <Cocoa/Cocoa.h>
#import <QuartzCore/QuartzCore.h>
#if MAC_OS_X_VERSION_MAX_ALLOWED >= 110000
#import <UniformTypeIdentifiers/UniformTypeIdentifiers.h>
#endif
#ifndef NO_CARBON_H
#import <Carbon/Carbon.h>
#endif
#undef TextStyle
#import <objc/runtime.h> /* for sel_isEqual() */

#ifndef _TKMACINT
#include "tkMacOSXInt.h"
#endif
#ifndef _TKMACDEFAULT
#include "tkMacOSXDefault.h"
#endif

/* Macros for Mac OS X API availability checking */
#define TK_IF_MAC_OS_X_API(vers, symbol, ...) \
	tk_if_mac_os_x_10_##vers(symbol != NULL, 1, __VA_ARGS__)
#define TK_ELSE_MAC_OS_X(vers, ...) \
	tk_else_mac_os_x_10_##vers(__VA_ARGS__)
#define TK_IF_MAC_OS_X_API_COND(vers, symbol, cond, ...) \
	tk_if_mac_os_x_10_##vers(symbol != NULL, cond, __VA_ARGS__)
#define TK_ELSE(...) \
	} else { __VA_ARGS__
#define TK_ENDIF \
	}
/* Private macros that implement the checking macros above */
#define tk_if_mac_os_x_yes(chk, cond, ...) \
	if (cond) { __VA_ARGS__
#define tk_else_mac_os_x_yes(...) \
	} else {
#define tk_if_mac_os_x_chk(chk, cond, ...) \
	if ((chk) && (cond)) { __VA_ARGS__
#define tk_else_mac_os_x_chk(...) \
	} else { __VA_ARGS__
#define tk_if_mac_os_x_no(chk, cond, ...) \
	if (0) {
#define tk_else_mac_os_x_no(...) \
	} else { __VA_ARGS__

/*
 * Macros for DEBUG_ASSERT_MESSAGE et al from Debugging.h.
 */

#undef kComponentSignatureString
#undef COMPONENT_SIGNATURE
#define kComponentSignatureString "TkMacOSX"
#define COMPONENT_SIGNATURE 'Tk  '

/*
 * Macros abstracting checks only active in a debug build.
 */

#ifdef TK_MAC_DEBUG
#define TKLog(f, ...) NSLog(f, ##__VA_ARGS__)

/*
 * Macro to do debug message output.
 */
#define TkMacOSXDbgMsg(m, ...) \
    do { \
	TKLog(@"%s:%d: %s(): " m, strrchr(__FILE__, '/')+1, \
		__LINE__, __func__, ##__VA_ARGS__); \
    } while (0)

/*
 * Macro to do debug API failure message output.
 */
#define TkMacOSXDbgOSErr(f, err) \
    do { \
	TkMacOSXDbgMsg("%s failed: %d", #f, (int)(err)); \
    } while (0)

/*
 * Macro to do very common check for noErr return from given API and output
 * debug message in case of failure.
 */
#define ChkErr(f, ...) ({ \
	OSStatus err_ = f(__VA_ARGS__); \
	if (err_ != noErr) { \
	    TkMacOSXDbgOSErr(f, err_); \
	} \
	err_;})

#else /* TK_MAC_DEBUG */
#define TKLog(f, ...)
#define TkMacOSXDbgMsg(m, ...)
#define TkMacOSXDbgOSErr(f, err)
#define ChkErr(f, ...) ({f(__VA_ARGS__);})
#endif /* TK_MAC_DEBUG */

/*
 * Macro abstracting use of TkMacOSXGetNamedSymbol to init named symbols.
 */

#define UNINITIALISED_SYMBOL	((void*)(-1L))
#define TkMacOSXInitNamedSymbol(module, ret, symbol, ...) \
    static ret (* symbol)(__VA_ARGS__) = UNINITIALISED_SYMBOL; \
    if (symbol == UNINITIALISED_SYMBOL) { \
	symbol = TkMacOSXGetNamedSymbol(STRINGIFY(module), \
		STRINGIFY(symbol)); \
    }

/*
 *  The structure of a 32-bit XEvent keycode on macOS. It may be viewed as
 *  an unsigned int or as having either two or three bitfields.
 */

typedef struct keycode_v_t {
    unsigned keychar: 22;    /* UCS-32 character */
    unsigned o_s: 2;         /* State of Option and Shift keys. */
    unsigned virt: 8;     /* 8-bit virtual keycode - identifies a key. */
} keycode_v;

typedef struct keycode_x_t {
    unsigned keychar: 22;     /* UCS-32 character */
    unsigned xvirtual: 10;    /* Combines o_s and virtual. This 10-bit integer
			       * is used as a key for looking up the character
			       * produced when pressing a key with a particular
			       * Shift and Option modifier state. */
} keycode_x;

typedef union MacKeycode_t {
  unsigned int uint;
  keycode_v v;
  keycode_x x;
} MacKeycode;

/*
 * Macros used in tkMacOSXKeyboard.c and tkMacOSXKeyEvent.c.
 * Note that 0x7f is del and 0xF8FF is the Apple Logo character.
 */

#define ON_KEYPAD(virt) ((virt >= 0x41) && (virt <= 0x5C))
#define IS_PRINTABLE(keychar) ((keychar >= 0x20) && (keychar != 0x7f) && \
                               ((keychar < 0xF700) || keychar >= 0xF8FF))

/*
 * An "index" is 2-bit bitfield showing the state of the Option and Shift
 * keys.  It is used as an index when building the keymaps and it
 * is the value of the o_s bitfield of a keycode_v.
 */

#define INDEX_SHIFT 1
#define INDEX_OPTION 2
#define INDEX2STATE(index) ((index & INDEX_SHIFT ? ShiftMask : 0) |	\
			    (index & INDEX_OPTION ? Mod2Mask : 0))
#define INDEX2CARBON(index) ((index & INDEX_SHIFT ? shiftKey : 0) |	\
			     (index & INDEX_OPTION ? optionKey : 0))
#define STATE2INDEX(state) ((state & ShiftMask ? INDEX_SHIFT : 0) |	\
			    (state & Mod2Mask ? INDEX_OPTION : 0))

/*
 * Special values for the virtual bitfield.  Actual virtual keycodes are < 128.
 */

#define NO_VIRTUAL 0xFF /* Not generated by a key or the NSText"InputClient. */
#define REPLACEMENT_VIRTUAL 0x80 /* A BMP char sent by the NSTextInputClient. */
#define NON_BMP_VIRTUAL 0x81 /* A non-BMP char sent by the NSTextInputClient. */

/*
 * A special character is used in the keycode for simulated modifier KeyPress
 * or KeyRelease XEvents.  It is near the end of the private-use range but
 * different from the UniChar 0xF8FF which Apple uses for their logo character.
 * A different special character is used for keys, like the Menu key, which do
 * not appear on Macintosh keyboards.
 */

#define MOD_KEYCHAR 0xF8FE
#define UNKNOWN_KEYCHAR 0xF8FD

/*
 * Structure encapsulating current drawing environment.
 */

typedef struct TkMacOSXDrawingContext {
    CGContextRef context;
    NSView *view;
    HIShapeRef clipRgn;
} TkMacOSXDrawingContext;

/*
 * Prototypes for TkMacOSXRegion.c.
 */

MODULE_SCOPE HIShapeRef	TkMacOSXGetNativeRegion(TkRegion r);
MODULE_SCOPE void	TkMacOSXSetWithNativeRegion(TkRegion r,
			    HIShapeRef rgn);
MODULE_SCOPE OSStatus	TkMacOSHIShapeDifferenceWithRect(
			    HIMutableShapeRef inShape, const CGRect *inRect);
MODULE_SCOPE int	TkMacOSXCountRectsInRegion(HIShapeRef shape);
MODULE_SCOPE void       TkMacOSXPrintRectsInRegion(HIShapeRef shape);
/*
 * Prototypes of TkAqua internal procs.
 */

MODULE_SCOPE void *	TkMacOSXGetNamedSymbol(const char *module,
			    const char *symbol);
MODULE_SCOPE void	TkMacOSXDisplayChanged(Display *display);
MODULE_SCOPE CGFloat	TkMacOSXZeroScreenHeight();
MODULE_SCOPE CGFloat	TkMacOSXZeroScreenTop();
MODULE_SCOPE int	TkMacOSXUseAntialiasedText(Tcl_Interp *interp,
			    int enable);
MODULE_SCOPE int	TkMacOSXInitCGDrawing(Tcl_Interp *interp, int enable,
			    int antiAlias);
MODULE_SCOPE int	TkMacOSXIsWindowZoomed(TkWindow *winPtr);
MODULE_SCOPE int	TkGenerateButtonEventForXPointer(Window window);
MODULE_SCOPE void       TkMacOSXDrawCGImage(Drawable d, GC gc, CGContextRef context,
			    CGImageRef image, unsigned long imageForeground,
			    unsigned long imageBackground, CGRect imageBounds,
			    CGRect srcBounds, CGRect dstBounds);
MODULE_SCOPE int	TkMacOSXSetupDrawingContext(Drawable d, GC gc,
			    TkMacOSXDrawingContext *dcPtr);
MODULE_SCOPE void	TkMacOSXRestoreDrawingContext(
			    TkMacOSXDrawingContext *dcPtr);
MODULE_SCOPE void	TkMacOSXSetColorInContext(GC gc, unsigned long pixel,
			    CGContextRef context);
#define TkMacOSXGetTkWindow(window) ((TkWindow *)Tk_MacOSXGetTkWindow(window))
#define TkMacOSXGetNSWindowForDrawable(drawable) ((NSWindow *)TkMacOSXDrawable(drawable))
#define TkMacOSXGetNSViewForDrawable(macWin) ((NSView *)Tk_MacOSXGetNSViewForDrawable((Drawable)(macWin)))
MODULE_SCOPE CGContextRef TkMacOSXGetCGContextForDrawable(Drawable drawable);
MODULE_SCOPE void	TkMacOSXWinCGBounds(TkWindow *winPtr, CGRect *bounds);
MODULE_SCOPE HIShapeRef	TkMacOSXGetClipRgn(Drawable drawable);
MODULE_SCOPE void	TkMacOSXInvalidateViewRegion(NSView *view,
			    HIShapeRef rgn);
MODULE_SCOPE NSImage*	TkMacOSXGetNSImageFromTkImage(Display *display,
			    Tk_Image image, int width, int height);
MODULE_SCOPE NSImage*	TkMacOSXGetNSImageFromBitmap(Display *display,
			    Pixmap bitmap, GC gc, int width, int height);
MODULE_SCOPE NSColor*	TkMacOSXGetNSColor(GC gc, unsigned long pixel);
MODULE_SCOPE NSFont*	TkMacOSXNSFontForFont(Tk_Font tkfont);
MODULE_SCOPE NSDictionary* TkMacOSXNSFontAttributesForFont(Tk_Font tkfont);
MODULE_SCOPE NSModalSession TkMacOSXGetModalSession(void);
MODULE_SCOPE void	TkMacOSXSelDeadWindow(TkWindow *winPtr);
MODULE_SCOPE void	TkMacOSXApplyWindowAttributes(TkWindow *winPtr,
			    NSWindow *macWindow);
MODULE_SCOPE Tcl_ObjCmdProc TkMacOSXStandardAboutPanelObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc TkMacOSXIconBitmapObjCmd;
MODULE_SCOPE void       TkMacOSXDrawSolidBorder(Tk_Window tkwin, GC gc,
			    int inset, int thickness);
MODULE_SCOPE int 	TkMacOSXServices_Init(Tcl_Interp *interp);
MODULE_SCOPE Tcl_ObjCmdProc TkMacOSXRegisterServiceWidgetObjCmd;
MODULE_SCOPE unsigned   TkMacOSXAddVirtual(unsigned int keycode);
MODULE_SCOPE void       TkMacOSXWinNSBounds(TkWindow *winPtr, NSView *view,
					    NSRect *bounds);
MODULE_SCOPE Bool       TkMacOSXInDarkMode(Tk_Window tkwin);
MODULE_SCOPE void	TkMacOSXDrawAllViews(void *clientData);
MODULE_SCOPE unsigned long TkMacOSXClearPixel(void);
MODULE_SCOPE NSString*  TkMacOSXOSTypeToUTI(OSType ostype);
MODULE_SCOPE NSImage*   TkMacOSXIconForFileType(NSString *filetype);

#pragma mark Private Objective-C Classes

#define VISIBILITY_HIDDEN __attribute__((visibility("hidden")))

enum { tkMainMenu = 1, tkApplicationMenu, tkWindowsMenu, tkHelpMenu};

VISIBILITY_HIDDEN
@interface TKMenu : NSMenu {
@private
    void *_tkMenu;
    NSUInteger _tkOffset, _tkItemCount, _tkSpecial;
}
- (void)setSpecial:(NSUInteger)special;
- (BOOL)isSpecial:(NSUInteger)special;
@end

@interface TKMenu(TKMenuDelegate) <NSMenuDelegate>
@end

VISIBILITY_HIDDEN
@interface TKApplication : NSApplication {
@private
    Tcl_Interp *_eventInterp;
    NSMenu *_servicesMenu;
    TKMenu *_defaultMainMenu, *_defaultApplicationMenu;
    NSMenuItem *_demoMenuItem;
    NSArray *_defaultApplicationMenuItems, *_defaultWindowsMenuItems;
    NSArray *_defaultHelpMenuItems, *_defaultFileMenuItems;
    NSAutoreleasePool *_mainPool;
    NSThread *_backgoundLoop;

#ifdef __i386__
    /* The Objective C runtime used on i386 requires this. */
    int _poolLock;
    int _macOSVersion;  /* 10000 * major + 100*minor */
    Bool _isDrawing;
    Bool _needsToDraw;
    Bool _tkLiveResizeEnded;
    TkWindow *_tkPointerWindow;
    TkWindow *_tkEventTarget;
    TkWindow *_tkDragTarget;
    unsigned int _tkButtonState;
#endif

}
@property int poolLock;
@property int macOSVersion;
@property Bool isDrawing;
@property Bool needsToDraw;
@property Bool tkLiveResizeEnded;

/*
 * Persistent state variables used by processMouseEvent.
 */

@property(nonatomic) TkWindow *tkPointerWindow;
@property(nonatomic) TkWindow *tkEventTarget;
@property(nonatomic) TkWindow *tkDragTarget;
@property unsigned int tkButtonState;

@end
@interface TKApplication(TKInit)
- (NSString *)tkFrameworkImagePath:(NSString*)image;
- (void)_resetAutoreleasePool;
- (void)_lockAutoreleasePool;
- (void)_unlockAutoreleasePool;
@end
@interface TKApplication(TKKeyboard)
- (void) keyboardChanged: (NSNotification *) notification;
@end
@interface TKApplication(TKWindowEvent) <NSApplicationDelegate>
- (void) _setupWindowNotifications;
@end
@interface TKApplication(TKDialog) <NSOpenSavePanelDelegate>
@end
@interface TKApplication(TKMenu)
- (void)tkSetMainMenu:(TKMenu *)menu;
@end
@interface TKApplication(TKMenus)
- (void) _setupMenus;
@end
@interface NSApplication(TKNotify)
/* We need to declare this hidden method. */
- (void) _modalSession: (NSModalSession) session sendEvent: (NSEvent *) event;
- (void) _runBackgroundLoop;
@end
@interface TKApplication(TKEvent)
- (NSEvent *)tkProcessEvent:(NSEvent *)theEvent;
@end
@interface TKApplication(TKMouseEvent)
- (NSEvent *)tkProcessMouseEvent:(NSEvent *)theEvent;
@end
@interface TKApplication(TKKeyEvent)
- (NSEvent *)tkProcessKeyEvent:(NSEvent *)theEvent;
@end
@interface TKApplication(TKClipboard)
- (void)tkProvidePasteboard:(TkDisplay *)dispPtr;
- (void)tkCheckPasteboard;
@end
@interface TKApplication(TKHLEvents)
- (void) terminate: (id) sender;
- (void) superTerminate: (id) sender;
- (void) preferences: (id) sender;
- (void) handleQuitApplicationEvent:   (NSAppleEventDescriptor *)event
		     withReplyEvent:   (NSAppleEventDescriptor *)replyEvent;
- (void) handleOpenApplicationEvent:   (NSAppleEventDescriptor *)event
		     withReplyEvent:   (NSAppleEventDescriptor *)replyEvent;
- (void) handleReopenApplicationEvent: (NSAppleEventDescriptor *)event
		       withReplyEvent: (NSAppleEventDescriptor *)replyEvent;
- (void) handleShowPreferencesEvent:   (NSAppleEventDescriptor *)event
		     withReplyEvent:   (NSAppleEventDescriptor *)replyEvent;
- (void) handleOpenDocumentsEvent:     (NSAppleEventDescriptor *)event
		   withReplyEvent:     (NSAppleEventDescriptor *)replyEvent;
- (void) handlePrintDocumentsEvent:    (NSAppleEventDescriptor *)event
		   withReplyEvent:     (NSAppleEventDescriptor *)replyEvent;
- (void) handleDoScriptEvent:          (NSAppleEventDescriptor *)event
		   withReplyEvent:     (NSAppleEventDescriptor *)replyEvent;
- (void)handleURLEvent:                (NSAppleEventDescriptor*)event
	           withReplyEvent:     (NSAppleEventDescriptor*)replyEvent;
@end

VISIBILITY_HIDDEN
/*
 * Subclass TKContentView from NSTextInputClient to enable composition and
 * input from the Character Palette.
 */

@interface TKContentView : NSView <NSTextInputClient>
{
@private
    NSString *privateWorkingText;
    Bool _tkNeedsDisplay;
    NSRect _tkDirtyRect;
    NSTrackingArea *trackingArea;
}
@property Bool tkNeedsDisplay;
@property NSRect tkDirtyRect;
@end

@interface TKContentView(TKKeyEvent)
- (void) deleteWorkingText;
- (void) cancelComposingText;
@end

@interface TKContentView(TKWindowEvent)
- (void) addTkDirtyRect: (NSRect) rect;
- (void) clearTkDirtyRect;
- (void) generateExposeEvents: (NSRect) rect;
- (void) tkToolbarButton: (id) sender;
@end

@interface NSWindow(TKWm)
- (NSPoint) tkConvertPointToScreen:(NSPoint)point;
- (NSPoint) tkConvertPointFromScreen:(NSPoint)point;
@end

VISIBILITY_HIDDEN
@interface TKWindow : NSWindow
{
#ifdef __i386__
    /* The Objective C runtime used on i386 requires this. */
    Window _tkWindow;
#endif
}
@property Window tkWindow;
@end

@interface TKWindow(TKWm)
- (void)    tkLayoutChanged;
@end

@interface TKDrawerWindow : NSWindow
{
    id _i1, _i2;
#ifdef __i386__
    /* The Objective C runtime used on i386 requires this. */
    Window _tkWindow;
#endif
}
@property Window tkWindow;
@end

@interface TKPanel : NSPanel
{
#ifdef __i386__
    /* The Objective C runtime used on i386 requires this. */
    Window _tkWindow;
#endif
}
@property Window tkWindow;
@end

#pragma mark NSMenu & NSMenuItem Utilities

@interface NSMenu(TKUtils)
+ (id)menuWithTitle:(NSString *)title;
+ (id)menuWithTitle:(NSString *)title menuItems:(NSArray *)items;
+ (id)menuWithTitle:(NSString *)title submenus:(NSArray *)submenus;
- (NSMenuItem *)itemWithSubmenu:(NSMenu *)submenu;
- (NSMenuItem *)itemInSupermenu;
@end

@interface NSMenuItem(TKUtils)
+ (id)itemWithSubmenu:(NSMenu *)submenu;
+ (id)itemWithTitle:(NSString *)title submenu:(NSMenu *)submenu;
+ (id)itemWithTitle:(NSString *)title action:(SEL)action;
+ (id)itemWithTitle:(NSString *)title action:(SEL)action
	target:(id)target;
+ (id)itemWithTitle:(NSString *)title action:(SEL)action
	keyEquivalent:(NSString *)keyEquivalent;
+ (id)itemWithTitle:(NSString *)title action:(SEL)action
	target:(id)target keyEquivalent:(NSString *)keyEquivalent;
+ (id)itemWithTitle:(NSString *)title action:(SEL)action
	keyEquivalent:(NSString *)keyEquivalent
	keyEquivalentModifierMask:(NSUInteger)keyEquivalentModifierMask;
+ (id)itemWithTitle:(NSString *)title action:(SEL)action
	target:(id)target keyEquivalent:(NSString *)keyEquivalent
	keyEquivalentModifierMask:(NSUInteger)keyEquivalentModifierMask;
@end

@interface NSColorPanel(TKDialog)
- (void) _setUseModalAppearance: (BOOL) flag;
@end

@interface NSFont(TKFont)
- (NSFont *) bestMatchingFontForCharacters: (const UTF16Char *) characters
	length: (NSUInteger) length attributes: (NSDictionary *) attributes
	actualCoveredLength: (NSUInteger *) coveredLength;
@end

/*
 * This method of NSApplication is not declared in NSApplication.h so we
 * declare it here to be a method of the TKMenu category.
 */

@interface NSApplication(TKMenu)
- (void) setAppleMenu: (NSMenu *) menu;
@end

/*
 * These methods are exposed because they are needed to prevent zombie windows
 * on systems with a TouchBar.  The TouchBar Key-Value observer holds a
 * reference to the key window, which prevents deallocation of the key window
 * when it is closed.
 */

@interface NSApplication(TkWm)
- (id) _setKeyWindow: (NSWindow *) window;
- (id) _setMainWindow: (NSWindow *) window;
@end


/*
 *---------------------------------------------------------------------------
 *
 * TKNSString --
 *
 * When Tcl is compiled with TCL_UTF_MAX = 3 (the default for 8.6) it cannot
 * deal directly with UTF-8 encoded non-BMP characters, since their UTF-8
 * encoding requires 4 bytes. Instead, when using these versions of Tcl, Tk
 * uses the CESU-8 encoding internally.  This encoding is similar to UTF-8
 * except that it allows encoding surrogate characters as 3-byte sequences
 * using the same algorithm which UTF-8 uses for non-surrogates.  This means
 * that a non-BMP character is encoded as a string of length 6.  Apple's
 * NSString class does not provide a constructor which accepts a CESU-8 encoded
 * byte sequence as initial data.  So we add a new class which does provide
 * such a constructor.  It also has a DString property which is a DString whose
 * string pointer is a byte sequence encoding the NSString with the current Tk
 * encoding, namely UTF-8 if TCL_UTF_MAX >= 4 or CESU-8 if TCL_UTF_MAX = 3.
 *
 *---------------------------------------------------------------------------
 */

@interface TKNSString:NSString {
@private
    Tcl_DString _ds;
    NSString *_string;
    const char *_UTF8String;
}
@property const char *UTF8String;
@property (readonly) Tcl_DString DString;
- (instancetype)initWithTclUtfBytes:(const void *)bytes
			     length:(NSUInteger)len;
@end

#endif /* _TKMACPRIV */

/*
 * Local Variables:
 * mode: objc
 * c-basic-offset: 4
 * fill-column: 79
 * coding: utf-8
 * End:
 */
