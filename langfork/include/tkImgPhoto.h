/*
 * tkImgPhoto.h --
 *
 *	Declarations for images of type "photo" for Tk.
 *
 * Copyright (c) 1994 The Australian National University.
 * Copyright (c) 1994-1997 Sun Microsystems, Inc.
 * Copyright (c) 2002-2008 Donal K. Fellows
 * Copyright (c) 2003 ActiveState Corporation.
 *
 * See the file "license.terms" for information on usage and redistribution of
 * this file, and for a DISCLAIMER OF ALL WARRANTIES.
 *
 * Author: Paul Mackerras (paulus@cs.anu.edu.au),
 *	   Department of Computer Science,
 *	   Australian National University.
 */

#include "tkInt.h"
#ifdef _WIN32
#include "tkWinInt.h"
#elif defined(__CYGWIN__)
#include "tkUnixInt.h"
#endif

/*
 * Forward declarations of the structures we define.
 */

#define PhotoModel PhotoMaster
typedef struct ColorTableId	ColorTableId;
typedef struct ColorTable	ColorTable;
typedef struct PhotoInstance	PhotoInstance;
typedef struct PhotoMaster	PhotoMaster;

/*
 * A signed 8-bit integral type. If chars are unsigned and the compiler isn't
 * an ANSI one, then we have to use short instead (which wastes space) to get
 * signed behavior.
 */

#if defined(__STDC__) || defined(_AIX)
    typedef signed char schar;
#else
#   ifndef __CHAR_UNSIGNED__
	typedef char schar;
#   else
	typedef short schar;
#   endif
#endif

/*
 * An unsigned 32-bit integral type, used for pixel values. We use int rather
 * than long here to accommodate those systems where longs are 64 bits.
 */

typedef unsigned int pixel;

/*
 * The maximum number of pixels to transmit to the server in a single
 * XPutImage call.
 */

#define MAX_PIXELS 65536

/*
 * The set of colors required to display a photo image in a window depends on:
 *	- the visual used by the window
 *	- the palette, which specifies how many levels of each primary color to
 *	  use, and
 *	- the gamma value for the image.
 *
 * Pixel values allocated for specific colors are valid only for the colormap
 * in which they were allocated. Sets of pixel values allocated for displaying
 * photos are re-used in other windows if possible, that is, if the display,
 * colormap, palette and gamma values match. A hash table is used to locate
 * these sets of pixel values, using the following data structure as key:
 */

struct ColorTableId {
    Display *display;		/* Qualifies the colormap resource ID. */
    Colormap colormap;		/* Colormap that the windows are using. */
    double gamma;		/* Gamma exponent value for images. */
    Tk_Uid palette;		/* Specifies how many shades of each primary
				 * we want to allocate. */
};

/*
 * For a particular (display, colormap, palette, gamma) combination, a data
 * structure of the following type is used to store the allocated pixel values
 * and other information:
 */

struct ColorTable {
    ColorTableId id;		/* Information used in selecting this color
				 * table. */
    int	flags;			/* See below. */
    int	refCount;		/* Number of instances using this map. */
    int liveRefCount;		/* Number of instances which are actually in
				 * use, using this map. */
    int	numColors;		/* Number of colors allocated for this map. */

    XVisualInfo	visualInfo;	/* Information about the visual for windows
				 * using this color table. */

    pixel redValues[256];	/* Maps 8-bit values of red intensity to a
				 * pixel value or index in pixelMap. */
    pixel greenValues[256];	/* Ditto for green intensity. */
    pixel blueValues[256];	/* Ditto for blue intensity. */
    unsigned long *pixelMap;	/* Actual pixel values allocated. */

    unsigned char colorQuant[3][256];
				/* Maps 8-bit intensities to quantized
				 * intensities. The first index is 0 for red,
				 * 1 for green, 2 for blue. */
};

/*
 * Bit definitions for the flags field of a ColorTable.
 * BLACK_AND_WHITE:		1 means only black and white colors are
 *				available.
 * COLOR_WINDOW:		1 means a full 3-D color cube has been
 *				allocated.
 * DISPOSE_PENDING:		1 means a call to DisposeColorTable has been
 *				scheduled as an idle handler, but it hasn't
 *				been invoked yet.
 * MAP_COLORS:			1 means pixel values should be mapped through
 *				pixelMap.
 */

#ifdef COLOR_WINDOW
#undef COLOR_WINDOW
#endif

#define BLACK_AND_WHITE		1
#define COLOR_WINDOW		2
#define DISPOSE_PENDING		4
#define MAP_COLORS		8

/*
 * Definition of the data associated with each photo image model.
 */

struct PhotoMaster {
    Tk_ImageMaster tkMaster;	/* Tk's token for image model. NULL means the
				 * image is being deleted. */
    Tcl_Interp *interp;		/* Interpreter associated with the application
				 * using this image. */
    Tcl_Command imageCmd;	/* Token for image command (used to delete it
				 * when the image goes away). NULL means the
				 * image command has already been deleted. */
    int	flags;			/* Sundry flags, defined below. */
    int	width, height;		/* Dimensions of image. */
    int userWidth, userHeight;	/* User-declared image dimensions. */
    Tk_Uid palette;		/* User-specified default palette for
				 * instances of this image. */
    double gamma;		/* Display gamma value to correct for. */
    char *fileString;		/* Name of file to read into image. */
    Tcl_Obj *dataString;	/* Object to use as contents of image. */
    Tcl_Obj *format;		/* User-specified format of data in image file
				 * or string value. */
    unsigned char *pix32;	/* Local storage for 32-bit image. */
    int ditherX, ditherY;	/* Location of first incorrectly dithered
				 * pixel in image. */
    TkRegion validRegion;	/* Tk region indicating which parts of the
				 * image have valid image data. */
    PhotoInstance *instancePtr;	/* First in the list of instances associated
				 * with this model. */
};

/*
 * Bit definitions for the flags field of a PhotoMaster.
 * COLOR_IMAGE:			1 means that the image has different color
 *				components.
 * IMAGE_CHANGED:		1 means that the instances of this image need
 *				to be redithered.
 * COMPLEX_ALPHA:		1 means that the instances of this image have
 *				alpha values that aren't 0 or 255, and so need
 *				the copy-merge-replace renderer .
 */

#define COLOR_IMAGE		1
#define IMAGE_CHANGED		2
#define COMPLEX_ALPHA		4

/*
 * Flag to OR with the compositing rule to indicate that the source, despite
 * having an alpha channel, has simple alpha.
 */

#define SOURCE_IS_SIMPLE_ALPHA_PHOTO 0x10000000

/*
 * The following data structure represents all of the instances of a photo
 * image in windows on a given screen that are using the same colormap.
 */

struct PhotoInstance {
    PhotoMaster *masterPtr;	/* Pointer to model for image. */
    Display *display;		/* Display for windows using this instance. */
    Colormap colormap;		/* The image may only be used in windows with
				 * this particular colormap. */
    PhotoInstance *nextPtr;	/* Pointer to the next instance in the list of
				 * instances associated with this model. */
    int refCount;		/* Number of instances using this structure. */
    Tk_Uid palette;		/* Palette for these particular instances. */
    double gamma;		/* Gamma value for these instances. */
    Tk_Uid defaultPalette;	/* Default palette to use if a palette is not
				 * specified for the model. */
    ColorTable *colorTablePtr;	/* Pointer to information about colors
				 * allocated for image display in windows like
				 * this one. */
    Pixmap pixels;		/* X pixmap containing dithered image. */
    int width, height;		/* Dimensions of the pixmap. */
    schar *error;		/* Error image, used in dithering. */
    XImage *imagePtr;		/* Image structure for converted pixels. */
    XVisualInfo visualInfo;	/* Information about the visual that these
				 * windows are using. */
    GC gc;			/* Graphics context for writing images to the
				 * pixmap. */
};

/*
 * Implementation of the Porter-Duff Source-Over compositing rule.
 */

#define PD_SRC_OVER(srcColor, srcAlpha, dstColor, dstAlpha) \
	(srcColor*srcAlpha/255) + dstAlpha*(255-srcAlpha)/255*dstColor/255
#define PD_SRC_OVER_ALPHA(srcAlpha, dstAlpha) \
	(srcAlpha + (255-srcAlpha)*dstAlpha/255)

#undef MIN
#define MIN(a, b)	((a) < (b)? (a): (b))
#undef MAX
#define MAX(a, b)	((a) > (b)? (a): (b))

/*
 * Declarations of functions shared between the different parts of the
 * photo image implementation.
 */

MODULE_SCOPE void	TkImgPhotoConfigureInstance(
			    PhotoInstance *instancePtr);
MODULE_SCOPE void	TkImgDisposeInstance(ClientData clientData);
MODULE_SCOPE void	TkImgPhotoInstanceSetSize(PhotoInstance *instancePtr);
MODULE_SCOPE ClientData	TkImgPhotoGet(Tk_Window tkwin, ClientData clientData);
MODULE_SCOPE void	TkImgDitherInstance(PhotoInstance *instancePtr, int x,
			    int y, int width, int height);
MODULE_SCOPE void	TkImgPhotoDisplay(ClientData clientData,
			    Display *display, Drawable drawable,
			    int imageX, int imageY, int width, int height,
			    int drawableX, int drawableY);
MODULE_SCOPE void	TkImgPhotoFree(ClientData clientData,
			    Display *display);
MODULE_SCOPE void	TkImgResetDither(PhotoInstance *instancePtr);

/*
 * Local Variables:
 * mode: c
 * c-basic-offset: 4
 * fill-column: 78
 * End:
 */
