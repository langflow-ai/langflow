/*
 * tkMacOSXKeysyms.h --
 *
 *      Contains data used for processing key events, some of which was
 *      moved from tkMacOSXKeyboard.c.
 *
 * Copyright (c) 1990-1994 The Regents of the University of California.
 * Copyright (c) 1994-1997 Sun Microsystems, Inc.
 * Copyright 2001-2009, Apple Inc.
 * Copyright (c) 2006-2009 Daniel A. Steffen <das@users.sourceforge.net>
 * Copyright (c) 2020 Marc Culler
 *
 * See the file "license.terms" for information on usage and redistribution
 * of this file, and for a DISCLAIMER OF ALL WARRANTIES.
 */

#ifndef TKMACOSXKEYSYMS_H
#define TKMACOSXKEYSYMS_H 1

/*
 * This table enumerates the keys on Mac keyboards which do not represent
 * letters.  This is static data -- these keys do not change when the keyboard
 * layout changes.  The unicode representation of a special key which is not a
 * modifier and does not have an ASCII code point lies in the reserved range
 * 0xF700 - 0xF8FF.
 *
 * The table includes every key listed in Apple's documentation of Function-Key
 * Unicodes which is not marked as "Not on most Macintosh keyboards", as well
 * as F20, which is reported to be usable in scripts even though it does not
 * appear on any Macintosh keyboard.
 */

typedef struct {
    int virt;	/* value of [NSEvent keyCode] */
    KeySym keysym;	/* X11 keysym */
    KeyCode keychar;	/* XEvent keycode & 0xFFFF */
} KeyInfo;

static const KeyInfo keyArray[] = {
    {36,	XK_Return,	NSNewlineCharacter},
    {48,	XK_Tab,		NSTabCharacter},
    {51,	XK_BackSpace,	NSDeleteCharacter},
    {52,	XK_Return,	NSNewlineCharacter},  /* Used on some Powerbooks */
    {53,	XK_Escape,	0x1B},
    {54,	XK_Meta_R,      MOD_KEYCHAR},
    {55,	XK_Meta_L,	MOD_KEYCHAR},
    {56,	XK_Shift_L,	MOD_KEYCHAR},
    {57,	XK_Caps_Lock,   MOD_KEYCHAR},
    {58,	XK_Alt_L,	MOD_KEYCHAR},
    {59,	XK_Control_L,	MOD_KEYCHAR},
    {60,	XK_Shift_R, 	MOD_KEYCHAR},
    {61,	XK_Alt_R,	MOD_KEYCHAR},
    {62,	XK_Control_R,	MOD_KEYCHAR},
    {63,	XK_Super_L,	MOD_KEYCHAR},
    {64,	XK_F17,		NSF17FunctionKey},
    {65,	XK_KP_Decimal,	'.'},
    {67,	XK_KP_Multiply, '*'},
    {69,	XK_KP_Add,	'+'},
    {71,	XK_Clear,       NSClearLineFunctionKey}, /* Numlock on PC */
    {75,	XK_KP_Divide,   '/'},
    {76,	XK_KP_Enter,	NSEnterCharacter},       /* Fn Return */
    {78,	XK_KP_Subtract, '-'},
    {79,	XK_F18,		NSF18FunctionKey},
    {80,	XK_F19,		NSF19FunctionKey},
    {81,	XK_KP_Equal,	'='},
    {82,	XK_KP_0,	'0'},
    {83,	XK_KP_1,	'1'},
    {84,	XK_KP_2,	'2'},
    {85,	XK_KP_3,	'3'},
    {86,	XK_KP_4,	'4'},
    {87,	XK_KP_5,	'5'},
    {88,	XK_KP_6,	'6'},
    {89,	XK_KP_7,	'7'},
    {90,	XK_F20,		NSF20FunctionKey}, /* For scripting only */
    {91,	XK_KP_8,	'8'},
    {92,	XK_KP_9,	'9'},
    {96,	XK_F5,		NSF5FunctionKey},
    {97,	XK_F6,		NSF6FunctionKey},
    {98,	XK_F7,		NSF7FunctionKey},
    {99,	XK_F3,		NSF3FunctionKey},
    {100,	XK_F8,		NSF8FunctionKey},
    {101,	XK_F9,		NSF9FunctionKey},
    {103,	XK_F11,		NSF11FunctionKey},
    {105,	XK_F13,		NSF13FunctionKey},
    {106,	XK_F16,		NSF16FunctionKey},
    {107,	XK_F14,		NSF14FunctionKey},
    {109,	XK_F10,		NSF10FunctionKey},
    {110,       XK_Menu,	UNKNOWN_KEYCHAR},
    {111,	XK_F12,		NSF12FunctionKey},
    {113,	XK_F15,		NSF15FunctionKey},
    {114,	XK_Help,	NSHelpFunctionKey},
    {115,	XK_Home,	NSHomeFunctionKey},     /* Fn Left */
    {116,	XK_Page_Up,	NSPageUpFunctionKey},   /* Fn Up */
    {117,	XK_Delete,	NSDeleteFunctionKey},   /* Fn Delete */
    {118,	XK_F4,		NSF4FunctionKey},
    {119,	XK_End,		NSEndFunctionKey},      /* Fn Right */
    {120,	XK_F2,		NSF2FunctionKey},
    {121,	XK_Page_Down,	NSPageDownFunctionKey}, /* Fn Down */
    {122,	XK_F1,		NSF1FunctionKey},
    {123,	XK_Left,	NSLeftArrowFunctionKey},
    {124,	XK_Right,	NSRightArrowFunctionKey},
    {125,	XK_Down,	NSDownArrowFunctionKey},
    {126,	XK_Up,		NSUpArrowFunctionKey},
    {0, 0, 0}
};

/*
 * X11 keysyms for modifier keys, in order.  This list includes keys
 * which do not appear on Apple keyboards, such as Shift_Lock and
 * Super_R.  While most systems don't provide events for the "fn"
 * function key, Apple does.  We map it to Super_L when processing a
 * FlagsChanged NSEvent.
 */

#define NUM_MOD_KEYCODES 14
static const KeyCode modKeyArray[NUM_MOD_KEYCODES] = {
    XK_Shift_L,
    XK_Shift_R,
    XK_Control_L,
    XK_Control_R,
    XK_Caps_Lock,
    XK_Shift_Lock,
    XK_Meta_L,
    XK_Meta_R,
    XK_Alt_L,
    XK_Alt_R,
    XK_Super_L,
    XK_Super_R,
    XK_Hyper_L,
    XK_Hyper_R,
};

/*
 * This table pairs X11 Keysyms for alphanumeric characters with the
 * unicode code point for that letter.
 * The data comes from http://www.cl.cam.ac.uk/~mgk25/ucs/keysyms.txt
 */

typedef struct KeysymInfo {
    KeySym keysym;
    KeyCode keycode;
} KeysymInfo;

const KeysymInfo keysymTable[] = {
    {0x0020, 0x0020}, /* space */
    {0x0021, 0x0021}, /* exclam */
    {0x0022, 0x0022}, /* quotedbl */
    {0x0023, 0x0023}, /* numbersign */
    {0x0024, 0x0024}, /* dollar */
    {0x0025, 0x0025}, /* percent */
    {0x0026, 0x0026}, /* ampersand */
    {0x0027, 0x0027}, /* apostrophe */
    {0x0028, 0x0028}, /* parenleft */
    {0x0029, 0x0029}, /* parenright */
    {0x002a, 0x002a}, /* asterisk */
    {0x002b, 0x002b}, /* plus */
    {0x002c, 0x002c}, /* comma */
    {0x002d, 0x002d}, /* minus */
    {0x002e, 0x002e}, /* period */
    {0x002f, 0x002f}, /* slash */
    {0x0030, 0x0030}, /* 0 */
    {0x0031, 0x0031}, /* 1 */
    {0x0032, 0x0032}, /* 2 */
    {0x0033, 0x0033}, /* 3 */
    {0x0034, 0x0034}, /* 4 */
    {0x0035, 0x0035}, /* 5 */
    {0x0036, 0x0036}, /* 6 */
    {0x0037, 0x0037}, /* 7 */
    {0x0038, 0x0038}, /* 8 */
    {0x0039, 0x0039}, /* 9 */
    {0x003a, 0x003a}, /* colon */
    {0x003b, 0x003b}, /* semicolon */
    {0x003c, 0x003c}, /* less */
    {0x003d, 0x003d}, /* equal */
    {0x003e, 0x003e}, /* greater */
    {0x003f, 0x003f}, /* question */
    {0x0040, 0x0040}, /* at */
    {0x0041, 0x0041}, /* A */
    {0x0042, 0x0042}, /* B */
    {0x0043, 0x0043}, /* C */
    {0x0044, 0x0044}, /* D */
    {0x0045, 0x0045}, /* E */
    {0x0046, 0x0046}, /* F */
    {0x0047, 0x0047}, /* G */
    {0x0048, 0x0048}, /* H */
    {0x0049, 0x0049}, /* I */
    {0x004a, 0x004a}, /* J */
    {0x004b, 0x004b}, /* K */
    {0x004c, 0x004c}, /* L */
    {0x004d, 0x004d}, /* M */
    {0x004e, 0x004e}, /* N */
    {0x004f, 0x004f}, /* O */
    {0x0050, 0x0050}, /* P */
    {0x0051, 0x0051}, /* Q */
    {0x0052, 0x0052}, /* R */
    {0x0053, 0x0053}, /* S */
    {0x0054, 0x0054}, /* T */
    {0x0055, 0x0055}, /* U */
    {0x0056, 0x0056}, /* V */
    {0x0057, 0x0057}, /* W */
    {0x0058, 0x0058}, /* X */
    {0x0059, 0x0059}, /* Y */
    {0x005a, 0x005a}, /* Z */
    {0x005b, 0x005b}, /* bracketleft */
    {0x005c, 0x005c}, /* backslash */
    {0x005d, 0x005d}, /* bracketright */
    {0x005e, 0x005e}, /* asciicircum */
    {0x005f, 0x005f}, /* underscore */
    {0x0060, 0x0060}, /* grave */
    {0x0061, 0x0061}, /* a */
    {0x0062, 0x0062}, /* b */
    {0x0063, 0x0063}, /* c */
    {0x0064, 0x0064}, /* d */
    {0x0065, 0x0065}, /* e */
    {0x0066, 0x0066}, /* f */
    {0x0067, 0x0067}, /* g */
    {0x0068, 0x0068}, /* h */
    {0x0069, 0x0069}, /* i */
    {0x006a, 0x006a}, /* j */
    {0x006b, 0x006b}, /* k */
    {0x006c, 0x006c}, /* l */
    {0x006d, 0x006d}, /* m */
    {0x006e, 0x006e}, /* n */
    {0x006f, 0x006f}, /* o */
    {0x0070, 0x0070}, /* p */
    {0x0071, 0x0071}, /* q */
    {0x0072, 0x0072}, /* r */
    {0x0073, 0x0073}, /* s */
    {0x0074, 0x0074}, /* t */
    {0x0075, 0x0075}, /* u */
    {0x0076, 0x0076}, /* v */
    {0x0077, 0x0077}, /* w */
    {0x0078, 0x0078}, /* x */
    {0x0079, 0x0079}, /* y */
    {0x007a, 0x007a}, /* z */
    {0x007b, 0x007b}, /* braceleft */
    {0x007c, 0x007c}, /* bar */
    {0x007d, 0x007d}, /* braceright */
    {0x007e, 0x007e}, /* asciitilde */
    {0x00a0, 0x00a0}, /* nobreakspace */
    {0x00a1, 0x00a1}, /* exclamdown */
    {0x00a2, 0x00a2}, /* cent */
    {0x00a3, 0x00a3}, /* sterling */
    {0x00a4, 0x00a4}, /* currency */
    {0x00a5, 0x00a5}, /* yen */
    {0x00a6, 0x00a6}, /* brokenbar */
    {0x00a7, 0x00a7}, /* section */
    {0x00a8, 0x00a8}, /* diaeresis */
    {0x00a9, 0x00a9}, /* copyright */
    {0x00aa, 0x00aa}, /* ordfeminine */
    {0x00ab, 0x00ab}, /* guillemotleft */
    {0x00ac, 0x00ac}, /* notsign */
    {0x00ad, 0x00ad}, /* hyphen */
    {0x00ae, 0x00ae}, /* registered */
    {0x00af, 0x00af}, /* macron */
    {0x00b0, 0x00b0}, /* degree */
    {0x00b1, 0x00b1}, /* plusminus */
    {0x00b2, 0x00b2}, /* twosuperior */
    {0x00b3, 0x00b3}, /* threesuperior */
    {0x00b4, 0x00b4}, /* acute */
    {0x00b5, 0x00b5}, /* mu */
    {0x00b6, 0x00b6}, /* paragraph */
    {0x00b7, 0x00b7}, /* periodcentered */
    {0x00b8, 0x00b8}, /* cedilla */
    {0x00b9, 0x00b9}, /* onesuperior */
    {0x00ba, 0x00ba}, /* masculine */
    {0x00bb, 0x00bb}, /* guillemotright */
    {0x00bc, 0x00bc}, /* onequarter */
    {0x00bd, 0x00bd}, /* onehalf */
    {0x00be, 0x00be}, /* threequarters */
    {0x00bf, 0x00bf}, /* questiondown */
    {0x00c0, 0x00c0}, /* Agrave */
    {0x00c1, 0x00c1}, /* Aacute */
    {0x00c2, 0x00c2}, /* Acircumflex */
    {0x00c3, 0x00c3}, /* Atilde */
    {0x00c4, 0x00c4}, /* Adiaeresis */
    {0x00c5, 0x00c5}, /* Aring */
    {0x00c6, 0x00c6}, /* AE */
    {0x00c7, 0x00c7}, /* Ccedilla */
    {0x00c8, 0x00c8}, /* Egrave */
    {0x00c9, 0x00c9}, /* Eacute */
    {0x00ca, 0x00ca}, /* Ecircumflex */
    {0x00cb, 0x00cb}, /* Ediaeresis */
    {0x00cc, 0x00cc}, /* Igrave */
    {0x00cd, 0x00cd}, /* Iacute */
    {0x00ce, 0x00ce}, /* Icircumflex */
    {0x00cf, 0x00cf}, /* Idiaeresis */
    {0x00d0, 0x00d0}, /* ETH */
    {0x00d1, 0x00d1}, /* Ntilde */
    {0x00d2, 0x00d2}, /* Ograve */
    {0x00d3, 0x00d3}, /* Oacute */
    {0x00d4, 0x00d4}, /* Ocircumflex */
    {0x00d5, 0x00d5}, /* Otilde */
    {0x00d6, 0x00d6}, /* Odiaeresis */
    {0x00d7, 0x00d7}, /* multiply */
    {0x00d8, 0x00d8}, /* Oslash */
    {0x00d9, 0x00d9}, /* Ugrave */
    {0x00da, 0x00da}, /* Uacute */
    {0x00db, 0x00db}, /* Ucircumflex */
    {0x00dc, 0x00dc}, /* Udiaeresis */
    {0x00dd, 0x00dd}, /* Yacute */
    {0x00de, 0x00de}, /* THORN */
    {0x00df, 0x00df}, /* ssharp */
    {0x00e0, 0x00e0}, /* agrave */
    {0x00e1, 0x00e1}, /* aacute */
    {0x00e2, 0x00e2}, /* acircumflex */
    {0x00e3, 0x00e3}, /* atilde */
    {0x00e4, 0x00e4}, /* adiaeresis */
    {0x00e5, 0x00e5}, /* aring */
    {0x00e6, 0x00e6}, /* ae */
    {0x00e7, 0x00e7}, /* ccedilla */
    {0x00e8, 0x00e8}, /* egrave */
    {0x00e9, 0x00e9}, /* eacute */
    {0x00ea, 0x00ea}, /* ecircumflex */
    {0x00eb, 0x00eb}, /* ediaeresis */
    {0x00ec, 0x00ec}, /* igrave */
    {0x00ed, 0x00ed}, /* iacute */
    {0x00ee, 0x00ee}, /* icircumflex */
    {0x00ef, 0x00ef}, /* idiaeresis */
    {0x00f0, 0x00f0}, /* eth */
    {0x00f1, 0x00f1}, /* ntilde */
    {0x00f2, 0x00f2}, /* ograve */
    {0x00f3, 0x00f3}, /* oacute */
    {0x00f4, 0x00f4}, /* ocircumflex */
    {0x00f5, 0x00f5}, /* otilde */
    {0x00f6, 0x00f6}, /* odiaeresis */
    {0x00f7, 0x00f7}, /* division */
    {0x00f8, 0x00f8}, /* oslash */
    {0x00f9, 0x00f9}, /* ugrave */
    {0x00fa, 0x00fa}, /* uacute */
    {0x00fb, 0x00fb}, /* ucircumflex */
    {0x00fc, 0x00fc}, /* udiaeresis */
    {0x00fd, 0x00fd}, /* yacute */
    {0x00fe, 0x00fe}, /* thorn */
    {0x00ff, 0x00ff}, /* ydiaeresis */
    {0x01a1, 0x0104}, /* Aogonek */
    {0x01a2, 0x02d8}, /* breve */
    {0x01a3, 0x0141}, /* Lstroke */
    {0x01a5, 0x013d}, /* Lcaron */
    {0x01a6, 0x015a}, /* Sacute */
    {0x01a9, 0x0160}, /* Scaron */
    {0x01aa, 0x015e}, /* Scedilla */
    {0x01ab, 0x0164}, /* Tcaron */
    {0x01ac, 0x0179}, /* Zacute */
    {0x01ae, 0x017d}, /* Zcaron */
    {0x01af, 0x017b}, /* Zabovedot */
    {0x01b1, 0x0105}, /* aogonek */
    {0x01b2, 0x02db}, /* ogonek */
    {0x01b3, 0x0142}, /* lstroke */
    {0x01b5, 0x013e}, /* lcaron */
    {0x01b6, 0x015b}, /* sacute */
    {0x01b7, 0x02c7}, /* caron */
    {0x01b9, 0x0161}, /* scaron */
    {0x01ba, 0x015f}, /* scedilla */
    {0x01bb, 0x0165}, /* tcaron */
    {0x01bc, 0x017a}, /* zacute */
    {0x01bd, 0x02dd}, /* doubleacute */
    {0x01be, 0x017e}, /* zcaron */
    {0x01bf, 0x017c}, /* zabovedot */
    {0x01c0, 0x0154}, /* Racute */
    {0x01c3, 0x0102}, /* Abreve */
    {0x01c5, 0x0139}, /* Lacute */
    {0x01c6, 0x0106}, /* Cacute */
    {0x01c8, 0x010c}, /* Ccaron */
    {0x01ca, 0x0118}, /* Eogonek */
    {0x01cc, 0x011a}, /* Ecaron */
    {0x01cf, 0x010e}, /* Dcaron */
    {0x01d0, 0x0110}, /* Dstroke */
    {0x01d1, 0x0143}, /* Nacute */
    {0x01d2, 0x0147}, /* Ncaron */
    {0x01d5, 0x0150}, /* Odoubleacute */
    {0x01d8, 0x0158}, /* Rcaron */
    {0x01d9, 0x016e}, /* Uring */
    {0x01db, 0x0170}, /* Udoubleacute */
    {0x01de, 0x0162}, /* Tcedilla */
    {0x01e0, 0x0155}, /* racute */
    {0x01e3, 0x0103}, /* abreve */
    {0x01e5, 0x013a}, /* lacute */
    {0x01e6, 0x0107}, /* cacute */
    {0x01e8, 0x010d}, /* ccaron */
    {0x01ea, 0x0119}, /* eogonek */
    {0x01ec, 0x011b}, /* ecaron */
    {0x01ef, 0x010f}, /* dcaron */
    {0x01f0, 0x0111}, /* dstroke */
    {0x01f1, 0x0144}, /* nacute */
    {0x01f2, 0x0148}, /* ncaron */
    {0x01f5, 0x0151}, /* odoubleacute */
    {0x01f8, 0x0159}, /* rcaron */
    {0x01f9, 0x016f}, /* uring */
    {0x01fb, 0x0171}, /* udoubleacute */
    {0x01fe, 0x0163}, /* tcedilla */
    {0x01ff, 0x02d9}, /* abovedot */
    {0x02a1, 0x0126}, /* Hstroke */
    {0x02a6, 0x0124}, /* Hcircumflex */
    {0x02a9, 0x0130}, /* Iabovedot */
    {0x02ab, 0x011e}, /* Gbreve */
    {0x02ac, 0x0134}, /* Jcircumflex */
    {0x02b1, 0x0127}, /* hstroke */
    {0x02b6, 0x0125}, /* hcircumflex */
    {0x02b9, 0x0131}, /* idotless */
    {0x02bb, 0x011f}, /* gbreve */
    {0x02bc, 0x0135}, /* jcircumflex */
    {0x02c5, 0x010a}, /* Cabovedot */
    {0x02c6, 0x0108}, /* Ccircumflex */
    {0x02d5, 0x0120}, /* Gabovedot */
    {0x02d8, 0x011c}, /* Gcircumflex */
    {0x02dd, 0x016c}, /* Ubreve */
    {0x02de, 0x015c}, /* Scircumflex */
    {0x02e5, 0x010b}, /* cabovedot */
    {0x02e6, 0x0109}, /* ccircumflex */
    {0x02f5, 0x0121}, /* gabovedot */
    {0x02f8, 0x011d}, /* gcircumflex */
    {0x02fd, 0x016d}, /* ubreve */
    {0x02fe, 0x015d}, /* scircumflex */
    {0x03a2, 0x0138}, /* kra */
    {0x03a3, 0x0156}, /* Rcedilla */
    {0x03a5, 0x0128}, /* Itilde */
    {0x03a6, 0x013b}, /* Lcedilla */
    {0x03aa, 0x0112}, /* Emacron */
    {0x03ab, 0x0122}, /* Gcedilla */
    {0x03ac, 0x0166}, /* Tslash */
    {0x03b3, 0x0157}, /* rcedilla */
    {0x03b5, 0x0129}, /* itilde */
    {0x03b6, 0x013c}, /* lcedilla */
    {0x03ba, 0x0113}, /* emacron */
    {0x03bb, 0x0123}, /* gcedilla */
    {0x03bc, 0x0167}, /* tslash */
    {0x03bd, 0x014a}, /* ENG */
    {0x03bf, 0x014b}, /* eng */
    {0x03c0, 0x0100}, /* Amacron */
    {0x03c7, 0x012e}, /* Iogonek */
    {0x03cc, 0x0116}, /* Eabovedot */
    {0x03cf, 0x012a}, /* Imacron */
    {0x03d1, 0x0145}, /* Ncedilla */
    {0x03d2, 0x014c}, /* Omacron */
    {0x03d3, 0x0136}, /* Kcedilla */
    {0x03d9, 0x0172}, /* Uogonek */
    {0x03dd, 0x0168}, /* Utilde */
    {0x03de, 0x016a}, /* Umacron */
    {0x03e0, 0x0101}, /* amacron */
    {0x03e7, 0x012f}, /* iogonek */
    {0x03ec, 0x0117}, /* eabovedot */
    {0x03ef, 0x012b}, /* imacron */
    {0x03f1, 0x0146}, /* ncedilla */
    {0x03f2, 0x014d}, /* omacron */
    {0x03f3, 0x0137}, /* kcedilla */
    {0x03f9, 0x0173}, /* uogonek */
    {0x03fd, 0x0169}, /* utilde */
    {0x03fe, 0x016b}, /* umacron */
    {0x047e, 0x203e}, /* overline */
    {0x04a1, 0x3002}, /* kana_fullstop */
    {0x04a2, 0x300c}, /* kana_openingbracket */
    {0x04a3, 0x300d}, /* kana_closingbracket */
    {0x04a4, 0x3001}, /* kana_comma */
    {0x04a5, 0x30fb}, /* kana_conjunctive */
    {0x04a6, 0x30f2}, /* kana_WO */
    {0x04a7, 0x30a1}, /* kana_a */
    {0x04a8, 0x30a3}, /* kana_i */
    {0x04a9, 0x30a5}, /* kana_u */
    {0x04aa, 0x30a7}, /* kana_e */
    {0x04ab, 0x30a9}, /* kana_o */
    {0x04ac, 0x30e3}, /* kana_ya */
    {0x04ad, 0x30e5}, /* kana_yu */
    {0x04ae, 0x30e7}, /* kana_yo */
    {0x04af, 0x30c3}, /* kana_tsu */
    {0x04b0, 0x30fc}, /* prolongedsound */
    {0x04b1, 0x30a2}, /* kana_A */
    {0x04b2, 0x30a4}, /* kana_I */
    {0x04b3, 0x30a6}, /* kana_U */
    {0x04b4, 0x30a8}, /* kana_E */
    {0x04b5, 0x30aa}, /* kana_O */
    {0x04b6, 0x30ab}, /* kana_KA */
    {0x04b7, 0x30ad}, /* kana_KI */
    {0x04b8, 0x30af}, /* kana_KU */
    {0x04b9, 0x30b1}, /* kana_KE */
    {0x04ba, 0x30b3}, /* kana_KO */
    {0x04bb, 0x30b5}, /* kana_SA */
    {0x04bc, 0x30b7}, /* kana_SHI */
    {0x04bd, 0x30b9}, /* kana_SU */
    {0x04be, 0x30bb}, /* kana_SE */
    {0x04bf, 0x30bd}, /* kana_SO */
    {0x04c0, 0x30bf}, /* kana_TA */
    {0x04c1, 0x30c1}, /* kana_CHI */
    {0x04c2, 0x30c4}, /* kana_TSU */
    {0x04c3, 0x30c6}, /* kana_TE */
    {0x04c4, 0x30c8}, /* kana_TO */
    {0x04c5, 0x30ca}, /* kana_NA */
    {0x04c6, 0x30cb}, /* kana_NI */
    {0x04c7, 0x30cc}, /* kana_NU */
    {0x04c8, 0x30cd}, /* kana_NE */
    {0x04c9, 0x30ce}, /* kana_NO */
    {0x04ca, 0x30cf}, /* kana_HA */
    {0x04cb, 0x30d2}, /* kana_HI */
    {0x04cc, 0x30d5}, /* kana_FU */
    {0x04cd, 0x30d8}, /* kana_HE */
    {0x04ce, 0x30db}, /* kana_HO */
    {0x04cf, 0x30de}, /* kana_MA */
    {0x04d0, 0x30df}, /* kana_MI */
    {0x04d1, 0x30e0}, /* kana_MU */
    {0x04d2, 0x30e1}, /* kana_ME */
    {0x04d3, 0x30e2}, /* kana_MO */
    {0x04d4, 0x30e4}, /* kana_YA */
    {0x04d5, 0x30e6}, /* kana_YU */
    {0x04d6, 0x30e8}, /* kana_YO */
    {0x04d7, 0x30e9}, /* kana_RA */
    {0x04d8, 0x30ea}, /* kana_RI */
    {0x04d9, 0x30eb}, /* kana_RU */
    {0x04da, 0x30ec}, /* kana_RE */
    {0x04db, 0x30ed}, /* kana_RO */
    {0x04dc, 0x30ef}, /* kana_WA */
    {0x04dd, 0x30f3}, /* kana_N */
    {0x04de, 0x309b}, /* voicedsound */
    {0x04df, 0x309c}, /* semivoicedsound */
    {0x05ac, 0x060c}, /* Arabic_comma */
    {0x05bb, 0x061b}, /* Arabic_semicolon */
    {0x05bf, 0x061f}, /* Arabic_question_mark */
    {0x05c1, 0x0621}, /* Arabic_hamza */
    {0x05c2, 0x0622}, /* Arabic_maddaonalef */
    {0x05c3, 0x0623}, /* Arabic_hamzaonalef */
    {0x05c4, 0x0624}, /* Arabic_hamzaonwaw */
    {0x05c5, 0x0625}, /* Arabic_hamzaunderalef */
    {0x05c6, 0x0626}, /* Arabic_hamzaonyeh */
    {0x05c7, 0x0627}, /* Arabic_alef */
    {0x05c8, 0x0628}, /* Arabic_beh */
    {0x05c9, 0x0629}, /* Arabic_tehmarbuta */
    {0x05ca, 0x062a}, /* Arabic_teh */
    {0x05cb, 0x062b}, /* Arabic_theh */
    {0x05cc, 0x062c}, /* Arabic_jeem */
    {0x05cd, 0x062d}, /* Arabic_hah */
    {0x05ce, 0x062e}, /* Arabic_khah */
    {0x05cf, 0x062f}, /* Arabic_dal */
    {0x05d0, 0x0630}, /* Arabic_thal */
    {0x05d1, 0x0631}, /* Arabic_ra */
    {0x05d2, 0x0632}, /* Arabic_zain */
    {0x05d3, 0x0633}, /* Arabic_seen */
    {0x05d4, 0x0634}, /* Arabic_sheen */
    {0x05d5, 0x0635}, /* Arabic_sad */
    {0x05d6, 0x0636}, /* Arabic_dad */
    {0x05d7, 0x0637}, /* Arabic_tah */
    {0x05d8, 0x0638}, /* Arabic_zah */
    {0x05d9, 0x0639}, /* Arabic_ain */
    {0x05da, 0x063a}, /* Arabic_ghain */
    {0x05e0, 0x0640}, /* Arabic_tatweel */
    {0x05e1, 0x0641}, /* Arabic_feh */
    {0x05e2, 0x0642}, /* Arabic_qaf */
    {0x05e3, 0x0643}, /* Arabic_kaf */
    {0x05e4, 0x0644}, /* Arabic_lam */
    {0x05e5, 0x0645}, /* Arabic_meem */
    {0x05e6, 0x0646}, /* Arabic_noon */
    {0x05e7, 0x0647}, /* Arabic_ha */
    {0x05e8, 0x0648}, /* Arabic_waw */
    {0x05e9, 0x0649}, /* Arabic_alefmaksura */
    {0x05ea, 0x064a}, /* Arabic_yeh */
    {0x05eb, 0x064b}, /* Arabic_fathatan */
    {0x05ec, 0x064c}, /* Arabic_dammatan */
    {0x05ed, 0x064d}, /* Arabic_kasratan */
    {0x05ee, 0x064e}, /* Arabic_fatha */
    {0x05ef, 0x064f}, /* Arabic_damma */
    {0x05f0, 0x0650}, /* Arabic_kasra */
    {0x05f1, 0x0651}, /* Arabic_shadda */
    {0x05f2, 0x0652}, /* Arabic_sukun */
    {0x06a1, 0x0452}, /* Serbian_dje */
    {0x06a2, 0x0453}, /* Macedonia_gje */
    {0x06a3, 0x0451}, /* Cyrillic_io */
    {0x06a4, 0x0454}, /* Ukrainian_ie */
    {0x06a5, 0x0455}, /* Macedonia_dse */
    {0x06a6, 0x0456}, /* Ukrainian_i */
    {0x06a7, 0x0457}, /* Ukrainian_yi */
    {0x06a8, 0x0458}, /* Cyrillic_je */
    {0x06a9, 0x0459}, /* Cyrillic_lje */
    {0x06aa, 0x045a}, /* Cyrillic_nje */
    {0x06ab, 0x045b}, /* Serbian_tshe */
    {0x06ac, 0x045c}, /* Macedonia_kje */
    {0x06ae, 0x045e}, /* Byelorussian_shortu */
    {0x06af, 0x045f}, /* Cyrillic_dzhe */
    {0x06b0, 0x2116}, /* numerosign */
    {0x06b1, 0x0402}, /* Serbian_DJE */
    {0x06b2, 0x0403}, /* Macedonia_GJE */
    {0x06b3, 0x0401}, /* Cyrillic_IO */
    {0x06b4, 0x0404}, /* Ukrainian_IE */
    {0x06b5, 0x0405}, /* Macedonia_DSE */
    {0x06b6, 0x0406}, /* Ukrainian_I */
    {0x06b7, 0x0407}, /* Ukrainian_YI */
    {0x06b8, 0x0408}, /* Cyrillic_JE */
    {0x06b9, 0x0409}, /* Cyrillic_LJE */
    {0x06ba, 0x040a}, /* Cyrillic_NJE */
    {0x06bb, 0x040b}, /* Serbian_TSHE */
    {0x06bc, 0x040c}, /* Macedonia_KJE */
    {0x06be, 0x040e}, /* Byelorussian_SHORTU */
    {0x06bf, 0x040f}, /* Cyrillic_DZHE */
    {0x06c0, 0x044e}, /* Cyrillic_yu */
    {0x06c1, 0x0430}, /* Cyrillic_a */
    {0x06c2, 0x0431}, /* Cyrillic_be */
    {0x06c3, 0x0446}, /* Cyrillic_tse */
    {0x06c4, 0x0434}, /* Cyrillic_de */
    {0x06c5, 0x0435}, /* Cyrillic_ie */
    {0x06c6, 0x0444}, /* Cyrillic_ef */
    {0x06c7, 0x0433}, /* Cyrillic_ghe */
    {0x06c8, 0x0445}, /* Cyrillic_ha */
    {0x06c9, 0x0438}, /* Cyrillic_i */
    {0x06ca, 0x0439}, /* Cyrillic_shorti */
    {0x06cb, 0x043a}, /* Cyrillic_ka */
    {0x06cc, 0x043b}, /* Cyrillic_el */
    {0x06cd, 0x043c}, /* Cyrillic_em */
    {0x06ce, 0x043d}, /* Cyrillic_en */
    {0x06cf, 0x043e}, /* Cyrillic_o */
    {0x06d0, 0x043f}, /* Cyrillic_pe */
    {0x06d1, 0x044f}, /* Cyrillic_ya */
    {0x06d2, 0x0440}, /* Cyrillic_er */
    {0x06d3, 0x0441}, /* Cyrillic_es */
    {0x06d4, 0x0442}, /* Cyrillic_te */
    {0x06d5, 0x0443}, /* Cyrillic_u */
    {0x06d6, 0x0436}, /* Cyrillic_zhe */
    {0x06d7, 0x0432}, /* Cyrillic_ve */
    {0x06d8, 0x044c}, /* Cyrillic_softsign */
    {0x06d9, 0x044b}, /* Cyrillic_yeru */
    {0x06da, 0x0437}, /* Cyrillic_ze */
    {0x06db, 0x0448}, /* Cyrillic_sha */
    {0x06dc, 0x044d}, /* Cyrillic_e */
    {0x06dd, 0x0449}, /* Cyrillic_shcha */
    {0x06de, 0x0447}, /* Cyrillic_che */
    {0x06df, 0x044a}, /* Cyrillic_hardsign */
    {0x06e0, 0x042e}, /* Cyrillic_YU */
    {0x06e1, 0x0410}, /* Cyrillic_A */
    {0x06e2, 0x0411}, /* Cyrillic_BE */
    {0x06e3, 0x0426}, /* Cyrillic_TSE */
    {0x06e4, 0x0414}, /* Cyrillic_DE */
    {0x06e5, 0x0415}, /* Cyrillic_IE */
    {0x06e6, 0x0424}, /* Cyrillic_EF */
    {0x06e7, 0x0413}, /* Cyrillic_GHE */
    {0x06e8, 0x0425}, /* Cyrillic_HA */
    {0x06e9, 0x0418}, /* Cyrillic_I */
    {0x06ea, 0x0419}, /* Cyrillic_SHORTI */
    {0x06eb, 0x041a}, /* Cyrillic_KA */
    {0x06ec, 0x041b}, /* Cyrillic_EL */
    {0x06ed, 0x041c}, /* Cyrillic_EM */
    {0x06ee, 0x041d}, /* Cyrillic_EN */
    {0x06ef, 0x041e}, /* Cyrillic_O */
    {0x06f0, 0x041f}, /* Cyrillic_PE */
    {0x06f1, 0x042f}, /* Cyrillic_YA */
    {0x06f2, 0x0420}, /* Cyrillic_ER */
    {0x06f3, 0x0421}, /* Cyrillic_ES */
    {0x06f4, 0x0422}, /* Cyrillic_TE */
    {0x06f5, 0x0423}, /* Cyrillic_U */
    {0x06f6, 0x0416}, /* Cyrillic_ZHE */
    {0x06f7, 0x0412}, /* Cyrillic_VE */
    {0x06f8, 0x042c}, /* Cyrillic_SOFTSIGN */
    {0x06f9, 0x042b}, /* Cyrillic_YERU */
    {0x06fa, 0x0417}, /* Cyrillic_ZE */
    {0x06fb, 0x0428}, /* Cyrillic_SHA */
    {0x06fc, 0x042d}, /* Cyrillic_E */
    {0x06fd, 0x0429}, /* Cyrillic_SHCHA */
    {0x06fe, 0x0427}, /* Cyrillic_CHE */
    {0x06ff, 0x042a}, /* Cyrillic_HARDSIGN */
    {0x07a1, 0x0386}, /* Greek_ALPHAaccent */
    {0x07a2, 0x0388}, /* Greek_EPSILONaccent */
    {0x07a3, 0x0389}, /* Greek_ETAaccent */
    {0x07a4, 0x038a}, /* Greek_IOTAaccent */
    {0x07a5, 0x03aa}, /* Greek_IOTAdiaeresis */
    {0x07a7, 0x038c}, /* Greek_OMICRONaccent */
    {0x07a8, 0x038e}, /* Greek_UPSILONaccent */
    {0x07a9, 0x03ab}, /* Greek_UPSILONdieresis */
    {0x07ab, 0x038f}, /* Greek_OMEGAaccent */
    {0x07ae, 0x0385}, /* Greek_accentdieresis */
    {0x07af, 0x2015}, /* Greek_horizbar */
    {0x07b1, 0x03ac}, /* Greek_alphaaccent */
    {0x07b2, 0x03ad}, /* Greek_epsilonaccent */
    {0x07b3, 0x03ae}, /* Greek_etaaccent */
    {0x07b4, 0x03af}, /* Greek_iotaaccent */
    {0x07b5, 0x03ca}, /* Greek_iotadieresis */
    {0x07b6, 0x0390}, /* Greek_iotaaccentdieresis */
    {0x07b7, 0x03cc}, /* Greek_omicronaccent */
    {0x07b8, 0x03cd}, /* Greek_upsilonaccent */
    {0x07b9, 0x03cb}, /* Greek_upsilondieresis */
    {0x07ba, 0x03b0}, /* Greek_upsilonaccentdieresis */
    {0x07bb, 0x03ce}, /* Greek_omegaaccent */
    {0x07c1, 0x0391}, /* Greek_ALPHA */
    {0x07c2, 0x0392}, /* Greek_BETA */
    {0x07c3, 0x0393}, /* Greek_GAMMA */
    {0x07c4, 0x0394}, /* Greek_DELTA */
    {0x07c5, 0x0395}, /* Greek_EPSILON */
    {0x07c6, 0x0396}, /* Greek_ZETA */
    {0x07c7, 0x0397}, /* Greek_ETA */
    {0x07c8, 0x0398}, /* Greek_THETA */
    {0x07c9, 0x0399}, /* Greek_IOTA */
    {0x07ca, 0x039a}, /* Greek_KAPPA */
    {0x07cb, 0x039b}, /* Greek_LAMDA */
    {0x07cc, 0x039c}, /* Greek_MU */
    {0x07cd, 0x039d}, /* Greek_NU */
    {0x07ce, 0x039e}, /* Greek_XI */
    {0x07cf, 0x039f}, /* Greek_OMICRON */
    {0x07d0, 0x03a0}, /* Greek_PI */
    {0x07d1, 0x03a1}, /* Greek_RHO */
    {0x07d2, 0x03a3}, /* Greek_SIGMA */
    {0x07d4, 0x03a4}, /* Greek_TAU */
    {0x07d5, 0x03a5}, /* Greek_UPSILON */
    {0x07d6, 0x03a6}, /* Greek_PHI */
    {0x07d7, 0x03a7}, /* Greek_CHI */
    {0x07d8, 0x03a8}, /* Greek_PSI */
    {0x07d9, 0x03a9}, /* Greek_OMEGA */
    {0x07e1, 0x03b1}, /* Greek_alpha */
    {0x07e2, 0x03b2}, /* Greek_beta */
    {0x07e3, 0x03b3}, /* Greek_gamma */
    {0x07e4, 0x03b4}, /* Greek_delta */
    {0x07e5, 0x03b5}, /* Greek_epsilon */
    {0x07e6, 0x03b6}, /* Greek_zeta */
    {0x07e7, 0x03b7}, /* Greek_eta */
    {0x07e8, 0x03b8}, /* Greek_theta */
    {0x07e9, 0x03b9}, /* Greek_iota */
    {0x07ea, 0x03ba}, /* Greek_kappa */
    {0x07eb, 0x03bb}, /* Greek_lambda */
    {0x07ec, 0x03bc}, /* Greek_mu */
    {0x07ed, 0x03bd}, /* Greek_nu */
    {0x07ee, 0x03be}, /* Greek_xi */
    {0x07ef, 0x03bf}, /* Greek_omicron */
    {0x07f0, 0x03c0}, /* Greek_pi */
    {0x07f1, 0x03c1}, /* Greek_rho */
    {0x07f2, 0x03c3}, /* Greek_sigma */
    {0x07f3, 0x03c2}, /* Greek_finalsmallsigma */
    {0x07f4, 0x03c4}, /* Greek_tau */
    {0x07f5, 0x03c5}, /* Greek_upsilon */
    {0x07f6, 0x03c6}, /* Greek_phi */
    {0x07f7, 0x03c7}, /* Greek_chi */
    {0x07f8, 0x03c8}, /* Greek_psi */
    {0x07f9, 0x03c9}, /* Greek_omega */
    {0x08a1, 0x23b7}, /* leftradical */
    {0x08a4, 0x2320}, /* topintegral */
    {0x08a5, 0x2321}, /* botintegral */
    {0x08a7, 0x23a1}, /* topleftsqbracket */
    {0x08a8, 0x23a3}, /* botleftsqbracket */
    {0x08a9, 0x23a4}, /* toprightsqbracket */
    {0x08aa, 0x23a6}, /* botrightsqbracket */
    {0x08ab, 0x239b}, /* topleftparens */
    {0x08ac, 0x239d}, /* botleftparens */
    {0x08ad, 0x239e}, /* toprightparens */
    {0x08ae, 0x23a0}, /* botrightparens */
    {0x08af, 0x23a8}, /* leftmiddlecurlybrace */
    {0x08b0, 0x23ac}, /* rightmiddlecurlybrace */
    {0x08bc, 0x2264}, /* lessthanequal */
    {0x08bd, 0x2260}, /* notequal */
    {0x08be, 0x2265}, /* greaterthanequal */
    {0x08bf, 0x222b}, /* integral */
    {0x08c0, 0x2234}, /* therefore */
    {0x08c1, 0x221d}, /* variation */
    {0x08c2, 0x221e}, /* infinity */
    {0x08c5, 0x2207}, /* nabla */
    {0x08c8, 0x223c}, /* approximate */
    {0x08c9, 0x2243}, /* similarequal */
    {0x08cd, 0x21d4}, /* ifonlyif */
    {0x08ce, 0x21d2}, /* implies */
    {0x08cf, 0x2261}, /* identical */
    {0x08d6, 0x221a}, /* radical */
    {0x08da, 0x2282}, /* includedin */
    {0x08db, 0x2283}, /* includes */
    {0x08dc, 0x2229}, /* intersection */
    {0x08dd, 0x222a}, /* union */
    {0x08de, 0x2227}, /* logicaland */
    {0x08df, 0x2228}, /* logicalor */
    {0x08ef, 0x2202}, /* partialderivative */
    {0x08f6, 0x0192}, /* function */
    {0x08fb, 0x2190}, /* leftarrow */
    {0x08fc, 0x2191}, /* uparrow */
    {0x08fd, 0x2192}, /* rightarrow */
    {0x08fe, 0x2193}, /* downarrow */
    {0x09e0, 0x25c6}, /* soliddiamond */
    {0x09e1, 0x2592}, /* checkerboard */
    {0x09e2, 0x2409}, /* ht */
    {0x09e3, 0x240c}, /* ff */
    {0x09e4, 0x240d}, /* cr */
    {0x09e5, 0x240a}, /* lf */
    {0x09e8, 0x2424}, /* nl */
    {0x09e9, 0x240b}, /* vt */
    {0x09ea, 0x2518}, /* lowrightcorner */
    {0x09eb, 0x2510}, /* uprightcorner */
    {0x09ec, 0x250c}, /* upleftcorner */
    {0x09ed, 0x2514}, /* lowleftcorner */
    {0x09ee, 0x253c}, /* crossinglines */
    {0x09ef, 0x23ba}, /* horizlinescan1 */
    {0x09f0, 0x23bb}, /* horizlinescan3 */
    {0x09f1, 0x2500}, /* horizlinescan5 */
    {0x09f2, 0x23bc}, /* horizlinescan7 */
    {0x09f3, 0x23bd}, /* horizlinescan9 */
    {0x09f4, 0x251c}, /* leftt */
    {0x09f5, 0x2524}, /* rightt */
    {0x09f6, 0x2534}, /* bott */
    {0x09f7, 0x252c}, /* topt */
    {0x09f8, 0x2502}, /* vertbar */
    {0x0aa1, 0x2003}, /* emspace */
    {0x0aa2, 0x2002}, /* enspace */
    {0x0aa3, 0x2004}, /* em3space */
    {0x0aa4, 0x2005}, /* em4space */
    {0x0aa5, 0x2007}, /* digitspace */
    {0x0aa6, 0x2008}, /* punctspace */
    {0x0aa7, 0x2009}, /* thinspace */
    {0x0aa8, 0x200a}, /* hairspace */
    {0x0aa9, 0x2014}, /* emdash */
    {0x0aaa, 0x2013}, /* endash */
    {0x0aae, 0x2026}, /* ellipsis */
    {0x0aaf, 0x2025}, /* doubbaselinedot */
    {0x0ab0, 0x2153}, /* onethird */
    {0x0ab1, 0x2154}, /* twothirds */
    {0x0ab2, 0x2155}, /* onefifth */
    {0x0ab3, 0x2156}, /* twofifths */
    {0x0ab4, 0x2157}, /* threefifths */
    {0x0ab5, 0x2158}, /* fourfifths */
    {0x0ab6, 0x2159}, /* onesixth */
    {0x0ab7, 0x215a}, /* fivesixths */
    {0x0ab8, 0x2105}, /* careof */
    {0x0abb, 0x2012}, /* figdash */
    {0x0ac3, 0x215b}, /* oneeighth */
    {0x0ac4, 0x215c}, /* threeeighths */
    {0x0ac5, 0x215d}, /* fiveeighths */
    {0x0ac6, 0x215e}, /* seveneighths */
    {0x0ac9, 0x2122}, /* trademark */
    {0x0ad0, 0x2018}, /* leftsinglequotemark */
    {0x0ad1, 0x2019}, /* rightsinglequotemark */
    {0x0ad2, 0x201c}, /* leftdoublequotemark */
    {0x0ad3, 0x201d}, /* rightdoublequotemark */
    {0x0ad4, 0x211e}, /* prescription */
    {0x0ad6, 0x2032}, /* minutes */
    {0x0ad7, 0x2033}, /* seconds */
    {0x0ad9, 0x271d}, /* latincross */
    {0x0aec, 0x2663}, /* club */
    {0x0aed, 0x2666}, /* diamond */
    {0x0aee, 0x2665}, /* heart */
    {0x0af0, 0x2720}, /* maltesecross */
    {0x0af1, 0x2020}, /* dagger */
    {0x0af2, 0x2021}, /* doubledagger */
    {0x0af3, 0x2713}, /* checkmark */
    {0x0af4, 0x2717}, /* ballotcross */
    {0x0af5, 0x266f}, /* musicalsharp */
    {0x0af6, 0x266d}, /* musicalflat */
    {0x0af7, 0x2642}, /* malesymbol */
    {0x0af8, 0x2640}, /* femalesymbol */
    {0x0af9, 0x260e}, /* telephone */
    {0x0afa, 0x2315}, /* telephonerecorder */
    {0x0afb, 0x2117}, /* phonographcopyright */
    {0x0afc, 0x2038}, /* caret */
    {0x0afd, 0x201a}, /* singlelowquotemark */
    {0x0afe, 0x201e}, /* doublelowquotemark */
    {0x0bc2, 0x22a5}, /* downtack */
    {0x0bc4, 0x230a}, /* downstile */
    {0x0bca, 0x2218}, /* jot */
    {0x0bcc, 0x2395}, /* quad */
    {0x0bce, 0x22a4}, /* uptack */
    {0x0bcf, 0x25cb}, /* circle */
    {0x0bd3, 0x2308}, /* upstile */
    {0x0bdc, 0x22a2}, /* lefttack */
    {0x0bfc, 0x22a3}, /* righttack */
    {0x0cdf, 0x2017}, /* hebrew_doublelowline */
    {0x0ce0, 0x05d0}, /* hebrew_aleph */
    {0x0ce1, 0x05d1}, /* hebrew_bet */
    {0x0ce2, 0x05d2}, /* hebrew_gimel */
    {0x0ce3, 0x05d3}, /* hebrew_dalet */
    {0x0ce4, 0x05d4}, /* hebrew_he */
    {0x0ce5, 0x05d5}, /* hebrew_waw */
    {0x0ce6, 0x05d6}, /* hebrew_zain */
    {0x0ce7, 0x05d7}, /* hebrew_chet */
    {0x0ce8, 0x05d8}, /* hebrew_tet */
    {0x0ce9, 0x05d9}, /* hebrew_yod */
    {0x0cea, 0x05da}, /* hebrew_finalkaph */
    {0x0ceb, 0x05db}, /* hebrew_kaph */
    {0x0cec, 0x05dc}, /* hebrew_lamed */
    {0x0ced, 0x05dd}, /* hebrew_finalmem */
    {0x0cee, 0x05de}, /* hebrew_mem */
    {0x0cef, 0x05df}, /* hebrew_finalnun */
    {0x0cf0, 0x05e0}, /* hebrew_nun */
    {0x0cf1, 0x05e1}, /* hebrew_samech */
    {0x0cf2, 0x05e2}, /* hebrew_ayin */
    {0x0cf3, 0x05e3}, /* hebrew_finalpe */
    {0x0cf4, 0x05e4}, /* hebrew_pe */
    {0x0cf5, 0x05e5}, /* hebrew_finalzade */
    {0x0cf6, 0x05e6}, /* hebrew_zade */
    {0x0cf7, 0x05e7}, /* hebrew_qoph */
    {0x0cf8, 0x05e8}, /* hebrew_resh */
    {0x0cf9, 0x05e9}, /* hebrew_shin */
    {0x0cfa, 0x05ea}, /* hebrew_taw */
    {0x0da1, 0x0e01}, /* Thai_kokai */
    {0x0da2, 0x0e02}, /* Thai_khokhai */
    {0x0da3, 0x0e03}, /* Thai_khokhuat */
    {0x0da4, 0x0e04}, /* Thai_khokhwai */
    {0x0da5, 0x0e05}, /* Thai_khokhon */
    {0x0da6, 0x0e06}, /* Thai_khorakhang */
    {0x0da7, 0x0e07}, /* Thai_ngongu */
    {0x0da8, 0x0e08}, /* Thai_chochan */
    {0x0da9, 0x0e09}, /* Thai_choching */
    {0x0daa, 0x0e0a}, /* Thai_chochang */
    {0x0dab, 0x0e0b}, /* Thai_soso */
    {0x0dac, 0x0e0c}, /* Thai_chochoe */
    {0x0dad, 0x0e0d}, /* Thai_yoying */
    {0x0dae, 0x0e0e}, /* Thai_dochada */
    {0x0daf, 0x0e0f}, /* Thai_topatak */
    {0x0db0, 0x0e10}, /* Thai_thothan */
    {0x0db1, 0x0e11}, /* Thai_thonangmontho */
    {0x0db2, 0x0e12}, /* Thai_thophuthao */
    {0x0db3, 0x0e13}, /* Thai_nonen */
    {0x0db4, 0x0e14}, /* Thai_dodek */
    {0x0db5, 0x0e15}, /* Thai_totao */
    {0x0db6, 0x0e16}, /* Thai_thothung */
    {0x0db7, 0x0e17}, /* Thai_thothahan */
    {0x0db8, 0x0e18}, /* Thai_thothong */
    {0x0db9, 0x0e19}, /* Thai_nonu */
    {0x0dba, 0x0e1a}, /* Thai_bobaimai */
    {0x0dbb, 0x0e1b}, /* Thai_popla */
    {0x0dbc, 0x0e1c}, /* Thai_phophung */
    {0x0dbd, 0x0e1d}, /* Thai_fofa */
    {0x0dbe, 0x0e1e}, /* Thai_phophan */
    {0x0dbf, 0x0e1f}, /* Thai_fofan */
    {0x0dc0, 0x0e20}, /* Thai_phosamphao */
    {0x0dc1, 0x0e21}, /* Thai_moma */
    {0x0dc2, 0x0e22}, /* Thai_yoyak */
    {0x0dc3, 0x0e23}, /* Thai_rorua */
    {0x0dc4, 0x0e24}, /* Thai_ru */
    {0x0dc5, 0x0e25}, /* Thai_loling */
    {0x0dc6, 0x0e26}, /* Thai_lu */
    {0x0dc7, 0x0e27}, /* Thai_wowaen */
    {0x0dc8, 0x0e28}, /* Thai_sosala */
    {0x0dc9, 0x0e29}, /* Thai_sorusi */
    {0x0dca, 0x0e2a}, /* Thai_sosua */
    {0x0dcb, 0x0e2b}, /* Thai_hohip */
    {0x0dcc, 0x0e2c}, /* Thai_lochula */
    {0x0dcd, 0x0e2d}, /* Thai_oang */
    {0x0dce, 0x0e2e}, /* Thai_honokhuk */
    {0x0dcf, 0x0e2f}, /* Thai_paiyannoi */
    {0x0dd0, 0x0e30}, /* Thai_saraa */
    {0x0dd1, 0x0e31}, /* Thai_maihanakat */
    {0x0dd2, 0x0e32}, /* Thai_saraaa */
    {0x0dd3, 0x0e33}, /* Thai_saraam */
    {0x0dd4, 0x0e34}, /* Thai_sarai */
    {0x0dd5, 0x0e35}, /* Thai_saraii */
    {0x0dd6, 0x0e36}, /* Thai_saraue */
    {0x0dd7, 0x0e37}, /* Thai_sarauee */
    {0x0dd8, 0x0e38}, /* Thai_sarau */
    {0x0dd9, 0x0e39}, /* Thai_sarauu */
    {0x0dda, 0x0e3a}, /* Thai_phinthu */
    {0x0ddf, 0x0e3f}, /* Thai_baht */
    {0x0de0, 0x0e40}, /* Thai_sarae */
    {0x0de1, 0x0e41}, /* Thai_saraae */
    {0x0de2, 0x0e42}, /* Thai_sarao */
    {0x0de3, 0x0e43}, /* Thai_saraaimaimuan */
    {0x0de4, 0x0e44}, /* Thai_saraaimaimalai */
    {0x0de5, 0x0e45}, /* Thai_lakkhangyao */
    {0x0de6, 0x0e46}, /* Thai_maiyamok */
    {0x0de7, 0x0e47}, /* Thai_maitaikhu */
    {0x0de8, 0x0e48}, /* Thai_maiek */
    {0x0de9, 0x0e49}, /* Thai_maitho */
    {0x0dea, 0x0e4a}, /* Thai_maitri */
    {0x0deb, 0x0e4b}, /* Thai_maichattawa */
    {0x0dec, 0x0e4c}, /* Thai_thanthakhat */
    {0x0ded, 0x0e4d}, /* Thai_nikhahit */
    {0x0df0, 0x0e50}, /* Thai_leksun */
    {0x0df1, 0x0e51}, /* Thai_leknung */
    {0x0df2, 0x0e52}, /* Thai_leksong */
    {0x0df3, 0x0e53}, /* Thai_leksam */
    {0x0df4, 0x0e54}, /* Thai_leksi */
    {0x0df5, 0x0e55}, /* Thai_lekha */
    {0x0df6, 0x0e56}, /* Thai_lekhok */
    {0x0df7, 0x0e57}, /* Thai_lekchet */
    {0x0df8, 0x0e58}, /* Thai_lekpaet */
    {0x0df9, 0x0e59}, /* Thai_lekkao */
    {0x13bc, 0x0152}, /* OE */
    {0x13bd, 0x0153}, /* oe */
    {0x13be, 0x0178}, /* Ydiaeresis */
    {0x20a0, 0x20a0}, /* EcuSign */
    {0x20a1, 0x20a1}, /* ColonSign */
    {0x20a2, 0x20a2}, /* CruzeiroSign */
    {0x20a3, 0x20a3}, /* FFrancSign */
    {0x20a4, 0x20a4}, /* LiraSign */
    {0x20a5, 0x20a5}, /* MillSign */
    {0x20a6, 0x20a6}, /* NairaSign */
    {0x20a7, 0x20a7}, /* PesetaSign */
    {0x20a8, 0x20a8}, /* RupeeSign */
    {0x20a9, 0x20a9}, /* WonSign */
    {0x20aa, 0x20aa}, /* NewSheqelSign */
    {0x20ab, 0x20ab}, /* DongSign */
    {0x20ac, 0x20ac}, /* EuroSign */
    {0x06ad, 0x0491}, /* Ukrainian_ghe_with_upturn */
    {0x06bd, 0x0490}, /* Ukrainian_GHE_WITH_UPTURN */
    {0x14a2, 0x0587}, /* Armenian_ligature_ew */
    {0x14a3, 0x0589}, /* Armenian_verjaket */
    {0x14aa, 0x055d}, /* Armenian_but */
    {0x14ad, 0x058a}, /* Armenian_yentamna */
    {0x14af, 0x055c}, /* Armenian_amanak */
    {0x14b0, 0x055b}, /* Armenian_shesht */
    {0x14b1, 0x055e}, /* Armenian_paruyk */
    {0x14b2, 0x0531}, /* Armenian_AYB */
    {0x14b3, 0x0561}, /* Armenian_ayb */
    {0x14b4, 0x0532}, /* Armenian_BEN */
    {0x14b5, 0x0562}, /* Armenian_ben */
    {0x14b6, 0x0533}, /* Armenian_GIM */
    {0x14b7, 0x0563}, /* Armenian_gim */
    {0x14b8, 0x0534}, /* Armenian_DA */
    {0x14b9, 0x0564}, /* Armenian_da */
    {0x14ba, 0x0535}, /* Armenian_YECH */
    {0x14bb, 0x0565}, /* Armenian_yech */
    {0x14bc, 0x0536}, /* Armenian_ZA */
    {0x14bd, 0x0566}, /* Armenian_za */
    {0x14be, 0x0537}, /* Armenian_E */
    {0x14bf, 0x0567}, /* Armenian_e */
    {0x14c0, 0x0538}, /* Armenian_AT */
    {0x14c1, 0x0568}, /* Armenian_at */
    {0x14c2, 0x0539}, /* Armenian_TO */
    {0x14c3, 0x0569}, /* Armenian_to */
    {0x14c4, 0x053a}, /* Armenian_ZHE */
    {0x14c5, 0x056a}, /* Armenian_zhe */
    {0x14c6, 0x053b}, /* Armenian_INI */
    {0x14c7, 0x056b}, /* Armenian_ini */
    {0x14c8, 0x053c}, /* Armenian_LYUN */
    {0x14c9, 0x056c}, /* Armenian_lyun */
    {0x14ca, 0x053d}, /* Armenian_KHE */
    {0x14cb, 0x056d}, /* Armenian_khe */
    {0x14cc, 0x053e}, /* Armenian_TSA */
    {0x14cd, 0x056e}, /* Armenian_tsa */
    {0x14ce, 0x053f}, /* Armenian_KEN */
    {0x14cf, 0x056f}, /* Armenian_ken */
    {0x14d0, 0x0540}, /* Armenian_HO */
    {0x14d1, 0x0570}, /* Armenian_ho */
    {0x14d2, 0x0541}, /* Armenian_DZA */
    {0x14d3, 0x0571}, /* Armenian_dza */
    {0x14d4, 0x0542}, /* Armenian_GHAT */
    {0x14d5, 0x0572}, /* Armenian_ghat */
    {0x14d6, 0x0543}, /* Armenian_TCHE */
    {0x14d7, 0x0573}, /* Armenian_tche */
    {0x14d8, 0x0544}, /* Armenian_MEN */
    {0x14d9, 0x0574}, /* Armenian_men */
    {0x14da, 0x0545}, /* Armenian_HI */
    {0x14db, 0x0575}, /* Armenian_hi */
    {0x14dc, 0x0546}, /* Armenian_NU */
    {0x14dd, 0x0576}, /* Armenian_nu */
    {0x14de, 0x0547}, /* Armenian_SHA */
    {0x14df, 0x0577}, /* Armenian_sha */
    {0x14e0, 0x0548}, /* Armenian_VO */
    {0x14e1, 0x0578}, /* Armenian_vo */
    {0x14e2, 0x0549}, /* Armenian_CHA */
    {0x14e3, 0x0579}, /* Armenian_cha */
    {0x14e4, 0x054a}, /* Armenian_PE */
    {0x14e5, 0x057a}, /* Armenian_pe */
    {0x14e6, 0x054b}, /* Armenian_JE */
    {0x14e7, 0x057b}, /* Armenian_je */
    {0x14e8, 0x054c}, /* Armenian_RA */
    {0x14e9, 0x057c}, /* Armenian_ra */
    {0x14ea, 0x054d}, /* Armenian_SE */
    {0x14eb, 0x057d}, /* Armenian_se */
    {0x14ec, 0x054e}, /* Armenian_VEV */
    {0x14ed, 0x057e}, /* Armenian_vev */
    {0x14ee, 0x054f}, /* Armenian_TYUN */
    {0x14ef, 0x057f}, /* Armenian_tyun */
    {0x14f0, 0x0550}, /* Armenian_RE */
    {0x14f1, 0x0580}, /* Armenian_re */
    {0x14f2, 0x0551}, /* Armenian_TSO */
    {0x14f3, 0x0581}, /* Armenian_tso */
    {0x14f4, 0x0552}, /* Armenian_VYUN */
    {0x14f5, 0x0582}, /* Armenian_vyun */
    {0x14f6, 0x0553}, /* Armenian_PYUR */
    {0x14f7, 0x0583}, /* Armenian_pyur */
    {0x14f8, 0x0554}, /* Armenian_KE */
    {0x14f9, 0x0584}, /* Armenian_ke */
    {0x14fa, 0x0555}, /* Armenian_O */
    {0x14fb, 0x0585}, /* Armenian_o */
    {0x14fc, 0x0556}, /* Armenian_FE */
    {0x14fd, 0x0586}, /* Armenian_fe */
    {0x14fe, 0x055a}, /* Armenian_apostrophe */
    {0x15d0, 0x10d0}, /* Georgian_an */
    {0x15d1, 0x10d1}, /* Georgian_ban */
    {0x15d2, 0x10d2}, /* Georgian_gan */
    {0x15d3, 0x10d3}, /* Georgian_don */
    {0x15d4, 0x10d4}, /* Georgian_en */
    {0x15d5, 0x10d5}, /* Georgian_vin */
    {0x15d6, 0x10d6}, /* Georgian_zen */
    {0x15d7, 0x10d7}, /* Georgian_tan */
    {0x15d8, 0x10d8}, /* Georgian_in */
    {0x15d9, 0x10d9}, /* Georgian_kan */
    {0x15da, 0x10da}, /* Georgian_las */
    {0x15db, 0x10db}, /* Georgian_man */
    {0x15dc, 0x10dc}, /* Georgian_nar */
    {0x15dd, 0x10dd}, /* Georgian_on */
    {0x15de, 0x10de}, /* Georgian_par */
    {0x15df, 0x10df}, /* Georgian_zhar */
    {0x15e0, 0x10e0}, /* Georgian_rae */
    {0x15e1, 0x10e1}, /* Georgian_san */
    {0x15e2, 0x10e2}, /* Georgian_tar */
    {0x15e3, 0x10e3}, /* Georgian_un */
    {0x15e4, 0x10e4}, /* Georgian_phar */
    {0x15e5, 0x10e5}, /* Georgian_khar */
    {0x15e6, 0x10e6}, /* Georgian_ghan */
    {0x15e7, 0x10e7}, /* Georgian_qar */
    {0x15e8, 0x10e8}, /* Georgian_shin */
    {0x15e9, 0x10e9}, /* Georgian_chin */
    {0x15ea, 0x10ea}, /* Georgian_can */
    {0x15eb, 0x10eb}, /* Georgian_jil */
    {0x15ec, 0x10ec}, /* Georgian_cil */
    {0x15ed, 0x10ed}, /* Georgian_char */
    {0x15ee, 0x10ee}, /* Georgian_xan */
    {0x15ef, 0x10ef}, /* Georgian_jhan */
    {0x15f0, 0x10f0}, /* Georgian_hae */
    {0x15f1, 0x10f1}, /* Georgian_he */
    {0x15f2, 0x10f2}, /* Georgian_hie */
    {0x15f3, 0x10f3}, /* Georgian_we */
    {0x15f4, 0x10f4}, /* Georgian_har */
    {0x15f5, 0x10f5}, /* Georgian_hoe */
    {0x15f6, 0x10f6}, /* Georgian_fi */
    {0x12a1, 0x1e02}, /* Babovedot */
    {0x12a2, 0x1e03}, /* babovedot */
    {0x12a6, 0x1e0a}, /* Dabovedot */
    {0x12a8, 0x1e80}, /* Wgrave */
    {0x12aa, 0x1e82}, /* Wacute */
    {0x12ab, 0x1e0b}, /* dabovedot */
    {0x12ac, 0x1ef2}, /* Ygrave */
    {0x12b0, 0x1e1e}, /* Fabovedot */
    {0x12b1, 0x1e1f}, /* fabovedot */
    {0x12b4, 0x1e40}, /* Mabovedot */
    {0x12b5, 0x1e41}, /* mabovedot */
    {0x12b7, 0x1e56}, /* Pabovedot */
    {0x12b8, 0x1e81}, /* wgrave */
    {0x12b9, 0x1e57}, /* pabovedot */
    {0x12ba, 0x1e83}, /* wacute */
    {0x12bb, 0x1e60}, /* Sabovedot */
    {0x12bc, 0x1ef3}, /* ygrave */
    {0x12bd, 0x1e84}, /* Wdiaeresis */
    {0x12be, 0x1e85}, /* wdiaeresis */
    {0x12bf, 0x1e61}, /* sabovedot */
    {0x12d0, 0x0174}, /* Wcircumflex */
    {0x12d7, 0x1e6a}, /* Tabovedot */
    {0x12de, 0x0176}, /* Ycircumflex */
    {0x12f0, 0x0175}, /* wcircumflex */
    {0x12f7, 0x1e6b}, /* tabovedot */
    {0x12fe, 0x0177}, /* ycircumflex */
    {0x0590, 0x06f0}, /* Farsi_0 */
    {0x0591, 0x06f1}, /* Farsi_1 */
    {0x0592, 0x06f2}, /* Farsi_2 */
    {0x0593, 0x06f3}, /* Farsi_3 */
    {0x0594, 0x06f4}, /* Farsi_4 */
    {0x0595, 0x06f5}, /* Farsi_5 */
    {0x0596, 0x06f6}, /* Farsi_6 */
    {0x0597, 0x06f7}, /* Farsi_7 */
    {0x0598, 0x06f8}, /* Farsi_8 */
    {0x0599, 0x06f9}, /* Farsi_9 */
    {0x05a5, 0x066a}, /* Arabic_percent */
    {0x05a6, 0x0670}, /* Arabic_superscript_alef */
    {0x05a7, 0x0679}, /* Arabic_tteh */
    {0x05a8, 0x067e}, /* Arabic_peh */
    {0x05a9, 0x0686}, /* Arabic_tcheh */
    {0x05aa, 0x0688}, /* Arabic_ddal */
    {0x05ab, 0x0691}, /* Arabic_rreh */
    {0x05ae, 0x06d4}, /* Arabic_fullstop */
    {0x05b0, 0x0660}, /* Arabic_0 */
    {0x05b1, 0x0661}, /* Arabic_1 */
    {0x05b2, 0x0662}, /* Arabic_2 */
    {0x05b3, 0x0663}, /* Arabic_3 */
    {0x05b4, 0x0664}, /* Arabic_4 */
    {0x05b5, 0x0665}, /* Arabic_5 */
    {0x05b6, 0x0666}, /* Arabic_6 */
    {0x05b7, 0x0667}, /* Arabic_7 */
    {0x05b8, 0x0668}, /* Arabic_8 */
    {0x05b9, 0x0669}, /* Arabic_9 */
    {0x05f3, 0x0653}, /* Arabic_madda_above */
    {0x05f4, 0x0654}, /* Arabic_hamza_above */
    {0x05f5, 0x0655}, /* Arabic_hamza_below */
    {0x05f6, 0x0698}, /* Arabic_jeh */
    {0x05f7, 0x06a4}, /* Arabic_veh */
    {0x05f8, 0x06a9}, /* Arabic_keheh */
    {0x05f9, 0x06af}, /* Arabic_gaf */
    {0x05fa, 0x06ba}, /* Arabic_noon_ghunna */
    {0x05fb, 0x06be}, /* Arabic_heh_doachashmee */
    {0x05fc, 0x06cc}, /* Farsi_yeh */
    {0x05fd, 0x06d2}, /* Arabic_yeh_baree */
    {0x05fe, 0x06c1}, /* Arabic_heh_goal */
    {0x0680, 0x0492}, /* Cyrillic_GHE_bar */
    {0x0681, 0x0496}, /* Cyrillic_ZHE_descender */
    {0x0682, 0x049a}, /* Cyrillic_KA_descender */
    {0x0683, 0x049c}, /* Cyrillic_KA_vertstroke */
    {0x0684, 0x04a2}, /* Cyrillic_EN_descender */
    {0x0685, 0x04ae}, /* Cyrillic_U_straight */
    {0x0686, 0x04b0}, /* Cyrillic_U_straight_bar */
    {0x0687, 0x04b2}, /* Cyrillic_HA_descender */
    {0x0688, 0x04b6}, /* Cyrillic_CHE_descender */
    {0x0689, 0x04b8}, /* Cyrillic_CHE_vertstroke */
    {0x068a, 0x04ba}, /* Cyrillic_SHHA */
    {0x068c, 0x04d8}, /* Cyrillic_SCHWA */
    {0x068d, 0x04e2}, /* Cyrillic_I_macron */
    {0x068e, 0x04e8}, /* Cyrillic_O_bar */
    {0x068f, 0x04ee}, /* Cyrillic_U_macron */
    {0x0690, 0x0493}, /* Cyrillic_ghe_bar */
    {0x0691, 0x0497}, /* Cyrillic_zhe_descender */
    {0x0692, 0x049b}, /* Cyrillic_ka_descender */
    {0x0693, 0x049d}, /* Cyrillic_ka_vertstroke */
    {0x0694, 0x04a3}, /* Cyrillic_en_descender */
    {0x0695, 0x04af}, /* Cyrillic_u_straight */
    {0x0696, 0x04b1}, /* Cyrillic_u_straight_bar */
    {0x0697, 0x04b3}, /* Cyrillic_ha_descender */
    {0x0698, 0x04b7}, /* Cyrillic_che_descender */
    {0x0699, 0x04b9}, /* Cyrillic_che_vertstroke */
    {0x069a, 0x04bb}, /* Cyrillic_shha */
    {0x069c, 0x04d9}, /* Cyrillic_schwa */
    {0x069d, 0x04e3}, /* Cyrillic_i_macron */
    {0x069e, 0x04e9}, /* Cyrillic_o_bar */
    {0x069f, 0x04ef}, /* Cyrillic_u_macron */
    {0x16a3, 0x1e8a}, /* Xabovedot */
    {0x16a6, 0x012c}, /* Ibreve */
    {0x16a9, 0x01b5}, /* Zstroke */
    {0x16aa, 0x01e6}, /* Gcaron */
    {0x16af, 0x019f}, /* Obarred */
    {0x16b3, 0x1e8b}, /* xabovedot */
    {0x16b6, 0x012d}, /* ibreve */
    {0x16b9, 0x01b6}, /* zstroke */
    {0x16ba, 0x01e7}, /* gcaron */
    {0x16bd, 0x01d2}, /* ocaron */
    {0x16bf, 0x0275}, /* obarred */
    {0x16c6, 0x018f}, /* SCHWA */
    {0x16f6, 0x0259}, /* schwa */
    {0x16d1, 0x1e36}, /* Lbelowdot */
    {0x16e1, 0x1e37}, /* lbelowdot */
    {0x1ea0, 0x1ea0}, /* Abelowdot */
    {0x1ea1, 0x1ea1}, /* abelowdot */
    {0x1ea2, 0x1ea2}, /* Ahook */
    {0x1ea3, 0x1ea3}, /* ahook */
    {0x1ea4, 0x1ea4}, /* Acircumflexacute */
    {0x1ea5, 0x1ea5}, /* acircumflexacute */
    {0x1ea6, 0x1ea6}, /* Acircumflexgrave */
    {0x1ea7, 0x1ea7}, /* acircumflexgrave */
    {0x1ea8, 0x1ea8}, /* Acircumflexhook */
    {0x1ea9, 0x1ea9}, /* acircumflexhook */
    {0x1eaa, 0x1eaa}, /* Acircumflextilde */
    {0x1eab, 0x1eab}, /* acircumflextilde */
    {0x1eac, 0x1eac}, /* Acircumflexbelowdot */
    {0x1ead, 0x1ead}, /* acircumflexbelowdot */
    {0x1eae, 0x1eae}, /* Abreveacute */
    {0x1eaf, 0x1eaf}, /* abreveacute */
    {0x1eb0, 0x1eb0}, /* Abrevegrave */
    {0x1eb1, 0x1eb1}, /* abrevegrave */
    {0x1eb2, 0x1eb2}, /* Abrevehook */
    {0x1eb3, 0x1eb3}, /* abrevehook */
    {0x1eb4, 0x1eb4}, /* Abrevetilde */
    {0x1eb5, 0x1eb5}, /* abrevetilde */
    {0x1eb6, 0x1eb6}, /* Abrevebelowdot */
    {0x1eb7, 0x1eb7}, /* abrevebelowdot */
    {0x1eb8, 0x1eb8}, /* Ebelowdot */
    {0x1eb9, 0x1eb9}, /* ebelowdot */
    {0x1eba, 0x1eba}, /* Ehook */
    {0x1ebb, 0x1ebb}, /* ehook */
    {0x1ebc, 0x1ebc}, /* Etilde */
    {0x1ebd, 0x1ebd}, /* etilde */
    {0x1ebe, 0x1ebe}, /* Ecircumflexacute */
    {0x1ebf, 0x1ebf}, /* ecircumflexacute */
    {0x1ec0, 0x1ec0}, /* Ecircumflexgrave */
    {0x1ec1, 0x1ec1}, /* ecircumflexgrave */
    {0x1ec2, 0x1ec2}, /* Ecircumflexhook */
    {0x1ec3, 0x1ec3}, /* ecircumflexhook */
    {0x1ec4, 0x1ec4}, /* Ecircumflextilde */
    {0x1ec5, 0x1ec5}, /* ecircumflextilde */
    {0x1ec6, 0x1ec6}, /* Ecircumflexbelowdot */
    {0x1ec7, 0x1ec7}, /* ecircumflexbelowdot */
    {0x1ec8, 0x1ec8}, /* Ihook */
    {0x1ec9, 0x1ec9}, /* ihook */
    {0x1eca, 0x1eca}, /* Ibelowdot */
    {0x1ecb, 0x1ecb}, /* ibelowdot */
    {0x1ecc, 0x1ecc}, /* Obelowdot */
    {0x1ecd, 0x1ecd}, /* obelowdot */
    {0x1ece, 0x1ece}, /* Ohook */
    {0x1ecf, 0x1ecf}, /* ohook */
    {0x1ed0, 0x1ed0}, /* Ocircumflexacute */
    {0x1ed1, 0x1ed1}, /* ocircumflexacute */
    {0x1ed2, 0x1ed2}, /* Ocircumflexgrave */
    {0x1ed3, 0x1ed3}, /* ocircumflexgrave */
    {0x1ed4, 0x1ed4}, /* Ocircumflexhook */
    {0x1ed5, 0x1ed5}, /* ocircumflexhook */
    {0x1ed6, 0x1ed6}, /* Ocircumflextilde */
    {0x1ed7, 0x1ed7}, /* ocircumflextilde */
    {0x1ed8, 0x1ed8}, /* Ocircumflexbelowdot */
    {0x1ed9, 0x1ed9}, /* ocircumflexbelowdot */
    {0x1eda, 0x1eda}, /* Ohornacute */
    {0x1edb, 0x1edb}, /* ohornacute */
    {0x1edc, 0x1edc}, /* Ohorngrave */
    {0x1edd, 0x1edd}, /* ohorngrave */
    {0x1ede, 0x1ede}, /* Ohornhook */
    {0x1edf, 0x1edf}, /* ohornhook */
    {0x1ee0, 0x1ee0}, /* Ohorntilde */
    {0x1ee1, 0x1ee1}, /* ohorntilde */
    {0x1ee2, 0x1ee2}, /* Ohornbelowdot */
    {0x1ee3, 0x1ee3}, /* ohornbelowdot */
    {0x1ee4, 0x1ee4}, /* Ubelowdot */
    {0x1ee5, 0x1ee5}, /* ubelowdot */
    {0x1ee6, 0x1ee6}, /* Uhook */
    {0x1ee7, 0x1ee7}, /* uhook */
    {0x1ee8, 0x1ee8}, /* Uhornacute */
    {0x1ee9, 0x1ee9}, /* uhornacute */
    {0x1eea, 0x1eea}, /* Uhorngrave */
    {0x1eeb, 0x1eeb}, /* uhorngrave */
    {0x1eec, 0x1eec}, /* Uhornhook */
    {0x1eed, 0x1eed}, /* uhornhook */
    {0x1eee, 0x1eee}, /* Uhorntilde */
    {0x1eef, 0x1eef}, /* uhorntilde */
    {0x1ef0, 0x1ef0}, /* Uhornbelowdot */
    {0x1ef1, 0x1ef1}, /* uhornbelowdot */
    {0x1ef4, 0x1ef4}, /* Ybelowdot */
    {0x1ef5, 0x1ef5}, /* ybelowdot */
    {0x1ef6, 0x1ef6}, /* Yhook */
    {0x1ef7, 0x1ef7}, /* yhook */
    {0x1ef8, 0x1ef8}, /* Ytilde */
    {0x1ef9, 0x1ef9}, /* ytilde */
    {0x1efa, 0x01a0}, /* Ohorn */
    {0x1efb, 0x01a1}, /* ohorn */
    {0x1efc, 0x01af}, /* Uhorn */
    {0x1efd, 0x01b0}, /* uhorn */
    {0, 0}
};

#endif
