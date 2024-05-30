/*
 * tkFont.h --
 *
 *	Declarations for interfaces between the generic and platform-specific
 *	parts of the font package. This information is not visible outside of
 *	the font package.
 *
 * Copyright (c) 1996-1997 Sun Microsystems, Inc.
 *
 * See the file "license.terms" for information on usage and redistribution of
 * this file, and for a DISCLAIMER OF ALL WARRANTIES.
 */

#ifndef _TKFONT
#define _TKFONT

/*
 * The following structure keeps track of the attributes of a font. It can be
 * used to keep track of either the desired attributes or the actual
 * attributes gotten when the font was instantiated.
 */

struct TkFontAttributes {
    Tk_Uid family;		/* Font family, or NULL to represent plaform-
				 * specific default system font. */
    double size;		/* Pointsize of font, 0.0 for default size, or
				 * negative number meaning pixel size. */
    int weight;			/* Weight flag; see below for def'n. */
    int slant;			/* Slant flag; see below for def'n. */
    int underline;		/* Non-zero for underline font. */
    int overstrike;		/* Non-zero for overstrike font. */
};

/*
 * Possible values for the "weight" field in a TkFontAttributes structure.
 * Weight is a subjective term and depends on what the company that created
 * the font considers bold.
 */

#define TK_FW_NORMAL	0
#define TK_FW_BOLD	1

#define TK_FW_UNKNOWN	-1	/* Unknown weight. This value is used for
				 * error checking and is never actually stored
				 * in the weight field. */

/*
 * Possible values for the "slant" field in a TkFontAttributes structure.
 */

#define TK_FS_ROMAN	0
#define TK_FS_ITALIC	1
#define TK_FS_OBLIQUE	2	/* This value is only used when parsing X font
				 * names to determine the closest match. It is
				 * only stored in the XLFDAttributes
				 * structure, never in the slant field of the
				 * TkFontAttributes. */

#define TK_FS_UNKNOWN	-1	/* Unknown slant. This value is used for error
				 * checking and is never actually stored in
				 * the slant field. */

/*
 * The following structure keeps track of the metrics for an instantiated
 * font. The metrics are the physical properties of the font itself.
 */

typedef struct TkFontMetrics {
    int	ascent;			/* From baseline to top of font. */
    int	descent;		/* From baseline to bottom of font. */
    int maxWidth;		/* Width of widest character in font. */
    int fixed;			/* Non-zero if this is a fixed-width font,
				 * 0 otherwise. */
} TkFontMetrics;

/*
 * The following structure is used to keep track of the generic information
 * about a font. Each platform-specific font is represented by a structure
 * with the following structure at its beginning, plus any platform-specific
 * stuff after that.
 */

typedef struct TkFont {
    /*
     * Fields used and maintained exclusively by generic code.
     */

    int resourceRefCount;	/* Number of active uses of this font (each
				 * active use corresponds to a call to
				 * Tk_AllocFontFromTable or Tk_GetFont). If
				 * this count is 0, then this TkFont structure
				 * is no longer valid and it isn't present in
				 * a hash table: it is being kept around only
				 * because there are objects referring to it.
				 * The structure is freed when
				 * resourceRefCount and objRefCount are both
				 * 0. */
    int objRefCount;		/* The number of Tcl objects that reference
				 * this structure. */
    Tcl_HashEntry *cacheHashPtr;/* Entry in font cache for this structure,
				 * used when deleting it. */
    Tcl_HashEntry *namedHashPtr;/* Pointer to hash table entry that
				 * corresponds to the named font that the
				 * tkfont was based on, or NULL if the tkfont
				 * was not based on a named font. */
    Screen *screen;		/* The screen where this font is valid. */
    int tabWidth;		/* Width of tabs in this font (pixels). */
    int	underlinePos;		/* Offset from baseline to origin of underline
				 * bar (used for drawing underlines on a
				 * non-underlined font). */
    int underlineHeight;	/* Height of underline bar (used for drawing
				 * underlines on a non-underlined font). */

    /*
     * Fields used in the generic code that are filled in by
     * platform-specific code.
     */

    Font fid;			/* For backwards compatibility with XGCValues
				 * structures. Remove when TkGCValues is
				 * implemented. */
    TkFontAttributes fa;	/* Actual font attributes obtained when the
				 * the font was created, as opposed to the
				 * desired attributes passed in to
				 * TkpGetFontFromAttributes(). The desired
				 * metrics can be determined from the string
				 * that was used to create this font. */
    TkFontMetrics fm;		/* Font metrics determined when font was
				 * created. */
    struct TkFont *nextPtr;	/* Points to the next TkFont structure with
				 * the same name. All fonts with the same name
				 * (but different displays) are chained
				 * together off a single entry in a hash
				 * table. */
} TkFont;

/*
 * The following structure is used to return attributes when parsing an XLFD.
 * The extra information is of interest to the Unix-specific code when
 * attempting to find the closest matching font.
 */

typedef struct TkXLFDAttributes {
    Tk_Uid foundry;		/* The foundry of the font. */
    int slant;			/* The tristate value for the slant, which is
				 * significant under X. */
    int setwidth;		/* The proportionate width, see below for
				 * definition. */
    Tk_Uid charset;		/* The actual charset string. */
} TkXLFDAttributes;

/*
 * Possible values for the "setwidth" field in a TkXLFDAttributes structure.
 * The setwidth is whether characters are considered wider or narrower than
 * normal.
 */

#define TK_SW_NORMAL	0
#define TK_SW_CONDENSE	1
#define TK_SW_EXPAND	2
#define TK_SW_UNKNOWN	3	/* Unknown setwidth. This value may be stored
				 * in the setwidth field. */

/*
 * The following defines specify the meaning of the fields in a fully
 * qualified XLFD.
 */

#define XLFD_FOUNDRY	    0
#define XLFD_FAMILY	    1
#define XLFD_WEIGHT	    2
#define XLFD_SLANT	    3
#define XLFD_SETWIDTH	    4
#define XLFD_ADD_STYLE	    5
#define XLFD_PIXEL_SIZE	    6
#define XLFD_POINT_SIZE	    7
#define XLFD_RESOLUTION_X   8
#define XLFD_RESOLUTION_Y   9
#define XLFD_SPACING	    10
#define XLFD_AVERAGE_WIDTH  11
#define XLFD_CHARSET	    12
#define XLFD_NUMFIELDS	    13	/* Number of fields in XLFD. */

/*
 * Helper macro. How to correctly round a double to a short.
 */

#define ROUND16(x)	((short) floor((x) + 0.5))

/*
 * Low-level API exported by generic code to platform-specific code.
 */

#define TkInitFontAttributes(fa)   memset((fa), 0, sizeof(TkFontAttributes));
#define TkInitXLFDAttributes(xa)   memset((xa), 0, sizeof(TkXLFDAttributes));

MODULE_SCOPE int	TkFontParseXLFD(const char *string,
			    TkFontAttributes *faPtr, TkXLFDAttributes *xaPtr);
MODULE_SCOPE const char *const * TkFontGetAliasList(const char *faceName);
MODULE_SCOPE const char *const *const * TkFontGetFallbacks(void);
MODULE_SCOPE double	TkFontGetPixels(Tk_Window tkwin, double size);
MODULE_SCOPE double	TkFontGetPoints(Tk_Window tkwin, double size);
MODULE_SCOPE const char *const * TkFontGetGlobalClass(void);
MODULE_SCOPE const char *const * TkFontGetSymbolClass(void);
MODULE_SCOPE int	TkCreateNamedFont(Tcl_Interp *interp, Tk_Window tkwin,
			    const char *name, TkFontAttributes *faPtr);
MODULE_SCOPE int	TkDeleteNamedFont(Tcl_Interp *interp,
			    Tk_Window tkwin, const char *name);
MODULE_SCOPE int	TkFontGetFirstTextLayout(Tk_TextLayout layout,
			    Tk_Font *font, char *dst);

/*
 * Low-level API exported by platform-specific code to generic code.
 */

MODULE_SCOPE void	TkpDeleteFont(TkFont *tkFontPtr);
MODULE_SCOPE void	TkpFontPkgInit(TkMainInfo *mainPtr);
MODULE_SCOPE TkFont *	TkpGetFontFromAttributes(TkFont *tkFontPtr,
			    Tk_Window tkwin, const TkFontAttributes *faPtr);
MODULE_SCOPE void	TkpGetFontFamilies(Tcl_Interp *interp,
			    Tk_Window tkwin);
MODULE_SCOPE TkFont *	TkpGetNativeFont(Tk_Window tkwin, const char *name);

#endif	/* _TKFONT */
