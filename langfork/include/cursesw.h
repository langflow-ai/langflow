// * This makes emacs happy -*-Mode: C++;-*-
// vile:cppmode
/****************************************************************************
 * Copyright 2019-2021,2022 Thomas E. Dickey                                *
 * Copyright 1998-2014,2017 Free Software Foundation, Inc.                  *
 *                                                                          *
 * Permission is hereby granted, free of charge, to any person obtaining a  *
 * copy of this software and associated documentation files (the            *
 * "Software"), to deal in the Software without restriction, including      *
 * without limitation the rights to use, copy, modify, merge, publish,      *
 * distribute, distribute with modifications, sublicense, and/or sell       *
 * copies of the Software, and to permit persons to whom the Software is    *
 * furnished to do so, subject to the following conditions:                 *
 *                                                                          *
 * The above copyright notice and this permission notice shall be included  *
 * in all copies or substantial portions of the Software.                   *
 *                                                                          *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS  *
 * OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF               *
 * MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.   *
 * IN NO EVENT SHALL THE ABOVE COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,   *
 * DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR    *
 * OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR    *
 * THE USE OR OTHER DEALINGS IN THE SOFTWARE.                               *
 *                                                                          *
 * Except as contained in this notice, the name(s) of the above copyright   *
 * holders shall not be used in advertising or otherwise to promote the     *
 * sale, use or other dealings in this Software without prior written       *
 * authorization.                                                           *
 ****************************************************************************/

#ifndef NCURSES_CURSESW_H_incl
#define NCURSES_CURSESW_H_incl 1

// $Id: cursesw.h,v 1.59 2022/08/20 20:52:15 tom Exp $

extern "C" {
#  include   <ncursesw/curses.h>
}

#if defined(BUILDING_NCURSES_CXX)
# define NCURSES_CXX_IMPEXP NCURSES_EXPORT_GENERAL_EXPORT
#else
# define NCURSES_CXX_IMPEXP NCURSES_EXPORT_GENERAL_IMPORT
#endif

#define NCURSES_CXX_WRAPPED_VAR(type,name) extern NCURSES_CXX_IMPEXP type NCURSES_PUBLIC_VAR(name)(void)

#define NCURSES_CXX_EXPORT(type) NCURSES_CXX_IMPEXP type NCURSES_API
#define NCURSES_CXX_EXPORT_VAR(type) NCURSES_CXX_IMPEXP type

#include <ncursesw/etip.h>

/* SCO 3.2v4 curses.h includes term.h, which defines lines as a macro.
   Undefine it here, because NCursesWindow uses lines as a method.  */
#undef lines

/* "Convert" macros to inlines. We'll define it as another symbol to avoid
 * conflict with library symbols.
 */
#undef UNDEF
#define UNDEF(name) CUR_ ##name

#ifdef addch
inline int UNDEF(addch)(chtype ch)  { return addch(ch); }
#undef addch
#define addch UNDEF(addch)
#endif

#ifdef addchstr
inline int UNDEF(addchstr)(chtype *at) { return addchstr(at); }
#undef addchstr
#define addchstr UNDEF(addchstr)
#endif

#ifdef addnstr
inline int UNDEF(addnstr)(const char *str, int n)
{ return addnstr(str, n); }
#undef addnstr
#define addnstr UNDEF(addnstr)
#endif

#ifdef addstr
inline int UNDEF(addstr)(const char * str)  { return addstr(str); }
#undef addstr
#define addstr UNDEF(addstr)
#endif

#ifdef attroff
inline int UNDEF(attroff)(chtype at) { return attroff(at); }
#undef attroff
#define attroff UNDEF(attroff)
#endif

#ifdef attron
inline int UNDEF(attron)(chtype at) { return attron(at); }
#undef attron
#define attron UNDEF(attron)
#endif

#ifdef attrset
inline chtype UNDEF(attrset)(chtype at) { return attrset(at); }
#undef attrset
#define attrset UNDEF(attrset)
#endif

#ifdef bkgd
inline int UNDEF(bkgd)(chtype ch) { return bkgd(ch); }
#undef bkgd
#define bkgd UNDEF(bkgd)
#endif

#ifdef bkgdset
inline void UNDEF(bkgdset)(chtype ch) { bkgdset(ch); }
#undef bkgdset
#define bkgdset UNDEF(bkgdset)
#endif

#ifdef border
inline int UNDEF(border)(chtype ls, chtype rs, chtype ts, chtype bs, chtype tl, chtype tr, chtype bl, chtype br)
{ return border(ls, rs, ts, bs, tl, tr, bl, br); }
#undef border
#define border UNDEF(border)
#endif

#ifdef box
inline int UNDEF(box)(WINDOW *win, int v, int h) { return box(win, v, h); }
#undef box
#define box UNDEF(box)
#endif

#ifdef chgat
inline int UNDEF(chgat)(int n, attr_t attr, NCURSES_PAIRS_T color, const void *opts) {
  return chgat(n, attr, color, opts); }
#undef chgat
#define chgat UNDEF(chgat)
#endif

#ifdef clear
inline int UNDEF(clear)()  { return clear(); }
#undef clear
#define clear UNDEF(clear)
#endif

#ifdef clearok
inline int UNDEF(clearok)(WINDOW* win, bool bf)  { return clearok(win, bf); }
#undef clearok
#define clearok UNDEF(clearok)
#else
extern "C" NCURSES_IMPEXP int NCURSES_API clearok(WINDOW*, bool);
#endif

#ifdef clrtobot
inline int UNDEF(clrtobot)()  { return clrtobot(); }
#undef clrtobot
#define clrtobot UNDEF(clrtobot)
#endif

#ifdef clrtoeol
inline int UNDEF(clrtoeol)()  { return clrtoeol(); }
#undef clrtoeol
#define clrtoeol UNDEF(clrtoeol)
#endif

#ifdef color_set
inline chtype UNDEF(color_set)(NCURSES_PAIRS_T p, void* opts) { return color_set(p, opts); }
#undef color_set
#define color_set UNDEF(color_set)
#endif

#ifdef crmode
inline int UNDEF(crmode)(void) { return crmode(); }
#undef crmode
#define crmode UNDEF(crmode)
#endif

#ifdef delch
inline int UNDEF(delch)()  { return delch(); }
#undef delch
#define delch UNDEF(delch)
#endif

#ifdef deleteln
inline int UNDEF(deleteln)()  { return deleteln(); }
#undef deleteln
#define deleteln UNDEF(deleteln)
#endif

#ifdef echochar
inline int UNDEF(echochar)(chtype ch)  { return echochar(ch); }
#undef echochar
#define echochar UNDEF(echochar)
#endif

#ifdef erase
inline int UNDEF(erase)()  { return erase(); }
#undef erase
#define erase UNDEF(erase)
#endif

#ifdef fixterm
inline int UNDEF(fixterm)(void) { return fixterm(); }
#undef fixterm
#define fixterm UNDEF(fixterm)
#endif

#ifdef flushok
inline int UNDEF(flushok)(WINDOW* _win, bool _bf)  {
  return flushok(_win, _bf); }
#undef flushok
#define flushok UNDEF(flushok)
#else
#define _no_flushok
#endif

#ifdef getattrs
inline int UNDEF(getattrs)(WINDOW *win) { return getattrs(win); }
#undef getattrs
#define getattrs UNDEF(getattrs)
#endif

#ifdef getbegyx
inline void UNDEF(getbegyx)(WINDOW* win, int& y, int& x) { getbegyx(win, y, x); }
#undef getbegyx
#define getbegyx UNDEF(getbegyx)
#endif

#ifdef getbkgd
inline chtype UNDEF(getbkgd)(const WINDOW *win) { return getbkgd(win); }
#undef getbkgd
#define getbkgd UNDEF(getbkgd)
#endif

#ifdef getch
inline int UNDEF(getch)()  { return getch(); }
#undef getch
#define getch UNDEF(getch)
#endif

#ifdef getmaxyx
inline void UNDEF(getmaxyx)(WINDOW* win, int& y, int& x) { getmaxyx(win, y, x); }
#undef getmaxyx
#define getmaxyx UNDEF(getmaxyx)
#endif

#ifdef getnstr
inline int UNDEF(getnstr)(char *_str, int n)  { return getnstr(_str, n); }
#undef getnstr
#define getnstr UNDEF(getnstr)
#endif

#ifdef getparyx
inline void UNDEF(getparyx)(WINDOW* win, int& y, int& x) { getparyx(win, y, x); }
#undef getparyx
#define getparyx UNDEF(getparyx)
#endif

#ifdef getstr
inline int UNDEF(getstr)(char *_str)  { return getstr(_str); }
#undef getstr
#define getstr UNDEF(getstr)
#endif

#ifdef getyx
inline void UNDEF(getyx)(const WINDOW* win, int& y, int& x) {
  getyx(win, y, x); }
#undef getyx
#define getyx UNDEF(getyx)
#endif

#ifdef hline
inline int UNDEF(hline)(chtype ch, int n) { return hline(ch, n); }
#undef hline
#define hline UNDEF(hline)
#endif

#ifdef inch
inline chtype UNDEF(inch)()  { return inch(); }
#undef inch
#define inch UNDEF(inch)
#endif

#ifdef inchstr
inline int UNDEF(inchstr)(chtype *str)  { return inchstr(str); }
#undef inchstr
#define inchstr UNDEF(inchstr)
#endif

#ifdef innstr
inline int UNDEF(innstr)(char *_str, int n)  { return innstr(_str, n); }
#undef innstr
#define innstr UNDEF(innstr)
#endif

#ifdef insch
inline int UNDEF(insch)(chtype c)  { return insch(c); }
#undef insch
#define insch UNDEF(insch)
#endif

#ifdef insdelln
inline int UNDEF(insdelln)(int n)  { return insdelln(n); }
#undef insdelln
#define insdelln UNDEF(insdelln)
#endif

#ifdef insertln
inline int UNDEF(insertln)()  { return insertln(); }
#undef insertln
#define insertln UNDEF(insertln)
#endif

#ifdef insnstr
inline int UNDEF(insnstr)(const char *_str, int n)  {
  return insnstr(_str, n); }
#undef insnstr
#define insnstr UNDEF(insnstr)
#endif

#ifdef insstr
inline int UNDEF(insstr)(const char *_str)  {
  return insstr(_str); }
#undef insstr
#define insstr UNDEF(insstr)
#endif

#ifdef instr
inline int UNDEF(instr)(char *_str)  { return instr(_str); }
#undef instr
#define instr UNDEF(instr)
#endif

#ifdef intrflush
inline void UNDEF(intrflush)(WINDOW *win, bool bf) { intrflush(); }
#undef intrflush
#define intrflush UNDEF(intrflush)
#endif

#ifdef is_linetouched
inline int UNDEF(is_linetouched)(WINDOW *w, int l)  { return is_linetouched(w,l); }
#undef is_linetouched
#define is_linetouched UNDEF(is_linetouched)
#endif

#ifdef leaveok
inline int UNDEF(leaveok)(WINDOW* win, bool bf)  { return leaveok(win, bf); }
#undef leaveok
#define leaveok UNDEF(leaveok)
#else
extern "C" NCURSES_IMPEXP int NCURSES_API leaveok(WINDOW* win, bool bf);
#endif

#ifdef move
inline int UNDEF(move)(int x, int y)  { return move(x, y); }
#undef move
#define move UNDEF(move)
#endif

#ifdef mvaddch
inline int UNDEF(mvaddch)(int y, int x, chtype ch)
{ return mvaddch(y, x, ch); }
#undef mvaddch
#define mvaddch UNDEF(mvaddch)
#endif

#ifdef mvaddnstr
inline int UNDEF(mvaddnstr)(int y, int x, const char *str, int n)
{ return mvaddnstr(y, x, str, n); }
#undef mvaddnstr
#define mvaddnstr UNDEF(mvaddnstr)
#endif

#ifdef mvaddstr
inline int UNDEF(mvaddstr)(int y, int x, const char * str)
{ return mvaddstr(y, x, str); }
#undef mvaddstr
#define mvaddstr UNDEF(mvaddstr)
#endif

#ifdef mvchgat
inline int UNDEF(mvchgat)(int y, int x, int n,
			  attr_t attr, NCURSES_PAIRS_T color, const void *opts) {
  return mvchgat(y, x, n, attr, color, opts); }
#undef mvchgat
#define mvchgat UNDEF(mvchgat)
#endif

#ifdef mvdelch
inline int UNDEF(mvdelch)(int y, int x) { return mvdelch(y, x);}
#undef mvdelch
#define mvdelch UNDEF(mvdelch)
#endif

#ifdef mvgetch
inline int UNDEF(mvgetch)(int y, int x) { return mvgetch(y, x);}
#undef mvgetch
#define mvgetch UNDEF(mvgetch)
#endif

#ifdef mvgetnstr
inline int UNDEF(mvgetnstr)(int y, int x, char *str, int n) {
  return mvgetnstr(y, x, str, n);}
#undef mvgetnstr
#define mvgetnstr UNDEF(mvgetnstr)
#endif

#ifdef mvgetstr
inline int UNDEF(mvgetstr)(int y, int x, char *str) {return mvgetstr(y, x, str);}
#undef mvgetstr
#define mvgetstr UNDEF(mvgetstr)
#endif

#ifdef mvinch
inline chtype UNDEF(mvinch)(int y, int x) { return mvinch(y, x);}
#undef mvinch
#define mvinch UNDEF(mvinch)
#endif

#ifdef mvinnstr
inline int UNDEF(mvinnstr)(int y, int x, char *_str, int n) {
  return mvinnstr(y, x, _str, n); }
#undef mvinnstr
#define mvinnstr UNDEF(mvinnstr)
#endif

#ifdef mvinsch
inline int UNDEF(mvinsch)(int y, int x, chtype c)
{ return mvinsch(y, x, c); }
#undef mvinsch
#define mvinsch UNDEF(mvinsch)
#endif

#ifdef mvinsnstr
inline int UNDEF(mvinsnstr)(int y, int x, const char *_str, int n) {
  return mvinsnstr(y, x, _str, n); }
#undef mvinsnstr
#define mvinsnstr UNDEF(mvinsnstr)
#endif

#ifdef mvinsstr
inline int UNDEF(mvinsstr)(int y, int x, const char *_str)  {
  return mvinsstr(y, x, _str); }
#undef mvinsstr
#define mvinsstr UNDEF(mvinsstr)
#endif

#ifdef mvwaddch
inline int UNDEF(mvwaddch)(WINDOW *win, int y, int x, const chtype ch)
{ return mvwaddch(win, y, x, ch); }
#undef mvwaddch
#define mvwaddch UNDEF(mvwaddch)
#endif

#ifdef mvwaddchnstr
inline int UNDEF(mvwaddchnstr)(WINDOW *win, int y, int x, const chtype *str, int n)
{ return mvwaddchnstr(win, y, x, str, n); }
#undef mvwaddchnstr
#define mvwaddchnstr UNDEF(mvwaddchnstr)
#endif

#ifdef mvwaddchstr
inline int UNDEF(mvwaddchstr)(WINDOW *win, int y, int x, const chtype *str)
{ return mvwaddchstr(win, y, x, str); }
#undef mvwaddchstr
#define mvwaddchstr UNDEF(mvwaddchstr)
#endif

#ifdef mvwaddnstr
inline int UNDEF(mvwaddnstr)(WINDOW *win, int y, int x, const char *str, int n)
{ return mvwaddnstr(win, y, x, str, n); }
#undef mvwaddnstr
#define mvwaddnstr UNDEF(mvwaddnstr)
#endif

#ifdef mvwaddstr
inline int UNDEF(mvwaddstr)(WINDOW *win, int y, int x, const char * str)
{ return mvwaddstr(win, y, x, str); }
#undef mvwaddstr
#define mvwaddstr UNDEF(mvwaddstr)
#endif

#ifdef mvwchgat
inline int UNDEF(mvwchgat)(WINDOW *win, int y, int x, int n,
			   attr_t attr, NCURSES_PAIRS_T color, const void *opts) {
  return mvwchgat(win, y, x, n, attr, color, opts); }
#undef mvwchgat
#define mvwchgat UNDEF(mvwchgat)
#endif

#ifdef mvwdelch
inline int UNDEF(mvwdelch)(WINDOW *win, int y, int x)
{ return mvwdelch(win, y, x); }
#undef mvwdelch
#define mvwdelch UNDEF(mvwdelch)
#endif

#ifdef mvwgetch
inline int UNDEF(mvwgetch)(WINDOW *win, int y, int x) { return mvwgetch(win, y, x);}
#undef mvwgetch
#define mvwgetch UNDEF(mvwgetch)
#endif

#ifdef mvwgetnstr
inline int UNDEF(mvwgetnstr)(WINDOW *win, int y, int x, char *str, int n)
{return mvwgetnstr(win, y, x, str, n);}
#undef mvwgetnstr
#define mvwgetnstr UNDEF(mvwgetnstr)
#endif

#ifdef mvwgetstr
inline int UNDEF(mvwgetstr)(WINDOW *win, int y, int x, char *str)
{return mvwgetstr(win, y, x, str);}
#undef mvwgetstr
#define mvwgetstr UNDEF(mvwgetstr)
#endif

#ifdef mvwhline
inline int UNDEF(mvwhline)(WINDOW *win, int y, int x, chtype c, int n) {
  return mvwhline(win, y, x, c, n); }
#undef mvwhline
#define mvwhline UNDEF(mvwhline)
#endif

#ifdef mvwinch
inline chtype UNDEF(mvwinch)(WINDOW *win, int y, int x) {
  return mvwinch(win, y, x);}
#undef mvwinch
#define mvwinch UNDEF(mvwinch)
#endif

#ifdef mvwinchnstr
inline int UNDEF(mvwinchnstr)(WINDOW *win, int y, int x, chtype *str, int n)  { return mvwinchnstr(win, y, x, str, n); }
#undef mvwinchnstr
#define mvwinchnstr UNDEF(mvwinchnstr)
#endif

#ifdef mvwinchstr
inline int UNDEF(mvwinchstr)(WINDOW *win, int y, int x, chtype *str)  { return mvwinchstr(win, y, x, str); }
#undef mvwinchstr
#define mvwinchstr UNDEF(mvwinchstr)
#endif

#ifdef mvwinnstr
inline int UNDEF(mvwinnstr)(WINDOW *win, int y, int x, char *_str, int n) {
  return mvwinnstr(win, y, x, _str, n); }
#undef mvwinnstr
#define mvwinnstr UNDEF(mvwinnstr)
#endif

#ifdef mvwinsch
inline int UNDEF(mvwinsch)(WINDOW *win, int y, int x, chtype c)
{ return mvwinsch(win, y, x, c); }
#undef mvwinsch
#define mvwinsch UNDEF(mvwinsch)
#endif

#ifdef mvwinsnstr
inline int UNDEF(mvwinsnstr)(WINDOW *w, int y, int x, const char *_str, int n) {
  return mvwinsnstr(w, y, x, _str, n); }
#undef mvwinsnstr
#define mvwinsnstr UNDEF(mvwinsnstr)
#endif

#ifdef mvwinsstr
inline int UNDEF(mvwinsstr)(WINDOW *w, int y, int x,  const char *_str)  {
  return mvwinsstr(w, y, x, _str); }
#undef mvwinsstr
#define mvwinsstr UNDEF(mvwinsstr)
#endif

#ifdef mvwvline
inline int UNDEF(mvwvline)(WINDOW *win, int y, int x, chtype c, int n) {
  return mvwvline(win, y, x, c, n); }
#undef mvwvline
#define mvwvline UNDEF(mvwvline)
#endif

#ifdef napms
inline void UNDEF(napms)(unsigned long x) { napms(x); }
#undef napms
#define napms UNDEF(napms)
#endif

#ifdef nocrmode
inline int UNDEF(nocrmode)(void) { return nocrmode(); }
#undef nocrmode
#define nocrmode UNDEF(nocrmode)
#endif

#ifdef nodelay
inline void UNDEF(nodelay)() { nodelay(); }
#undef nodelay
#define nodelay UNDEF(nodelay)
#endif

#ifdef redrawwin
inline int UNDEF(redrawwin)(WINDOW *win)  { return redrawwin(win); }
#undef redrawwin
#define redrawwin UNDEF(redrawwin)
#endif

#ifdef refresh
inline int UNDEF(refresh)()  { return refresh(); }
#undef refresh
#define refresh UNDEF(refresh)
#endif

#ifdef resetterm
inline int UNDEF(resetterm)(void) { return resetterm(); }
#undef resetterm
#define resetterm UNDEF(resetterm)
#endif

#ifdef saveterm
inline int UNDEF(saveterm)(void) { return saveterm(); }
#undef saveterm
#define saveterm UNDEF(saveterm)
#endif

#ifdef scrl
inline int UNDEF(scrl)(int l) { return scrl(l); }
#undef scrl
#define scrl UNDEF(scrl)
#endif

#ifdef scroll
inline int UNDEF(scroll)(WINDOW *win) { return scroll(win); }
#undef scroll
#define scroll UNDEF(scroll)
#endif

#ifdef scrollok
inline int UNDEF(scrollok)(WINDOW* win, bool bf)  { return scrollok(win, bf); }
#undef scrollok
#define scrollok UNDEF(scrollok)
#else
#if	defined(__NCURSES_H)
extern "C" NCURSES_IMPEXP int NCURSES_API scrollok(WINDOW*, bool);
#else
extern "C" NCURSES_IMPEXP int NCURSES_API scrollok(WINDOW*, char);
#endif
#endif

#ifdef setscrreg
inline int UNDEF(setscrreg)(int t, int b) { return setscrreg(t, b); }
#undef setscrreg
#define setscrreg UNDEF(setscrreg)
#endif

#ifdef standend
inline int UNDEF(standend)()  { return standend(); }
#undef standend
#define standend UNDEF(standend)
#endif

#ifdef standout
inline int UNDEF(standout)()  { return standout(); }
#undef standout
#define standout UNDEF(standout)
#endif

#ifdef subpad
inline WINDOW *UNDEF(subpad)(WINDOW *p, int l, int c, int y, int x)
{ return derwin(p, l, c, y, x); }
#undef subpad
#define subpad UNDEF(subpad)
#endif

#ifdef timeout
inline void UNDEF(timeout)(int delay) { timeout(delay); }
#undef timeout
#define timeout UNDEF(timeout)
#endif

#ifdef touchline
inline int UNDEF(touchline)(WINDOW *win, int s, int c)
{ return touchline(win, s, c); }
#undef touchline
#define touchline UNDEF(touchline)
#endif

#ifdef touchwin
inline int UNDEF(touchwin)(WINDOW *win) { return touchwin(win); }
#undef touchwin
#define touchwin UNDEF(touchwin)
#endif

#ifdef untouchwin
inline int UNDEF(untouchwin)(WINDOW *win) { return untouchwin(win); }
#undef untouchwin
#define untouchwin UNDEF(untouchwin)
#endif

#ifdef vline
inline int UNDEF(vline)(chtype ch, int n) { return vline(ch, n); }
#undef vline
#define vline UNDEF(vline)
#endif

#ifdef waddchstr
inline int UNDEF(waddchstr)(WINDOW *win, chtype *at) { return waddchstr(win, at); }
#undef waddchstr
#define waddchstr UNDEF(waddchstr)
#endif

#ifdef waddstr
inline int UNDEF(waddstr)(WINDOW *win, char *str) { return waddstr(win, str); }
#undef waddstr
#define waddstr UNDEF(waddstr)
#endif

#ifdef wattroff
inline int UNDEF(wattroff)(WINDOW *win, int att) { return wattroff(win, att); }
#undef wattroff
#define wattroff UNDEF(wattroff)
#endif

#ifdef wattrset
inline int UNDEF(wattrset)(WINDOW *win, int att) { return wattrset(win, att); }
#undef wattrset
#define wattrset UNDEF(wattrset)
#endif

#ifdef winch
inline chtype UNDEF(winch)(const WINDOW* win) { return winch(win); }
#undef winch
#define winch UNDEF(winch)
#endif

#ifdef winchnstr
inline int UNDEF(winchnstr)(WINDOW *win, chtype *str, int n)  { return winchnstr(win, str, n); }
#undef winchnstr
#define winchnstr UNDEF(winchnstr)
#endif

#ifdef winchstr
inline int UNDEF(winchstr)(WINDOW *win, chtype *str)  { return winchstr(win, str); }
#undef winchstr
#define winchstr UNDEF(winchstr)
#endif

#ifdef winsstr
inline int UNDEF(winsstr)(WINDOW *w, const char *_str)  {
  return winsstr(w, _str); }
#undef winsstr
#define winsstr UNDEF(winsstr)
#endif

#ifdef wstandend
inline int UNDEF(wstandend)(WINDOW *win)  { return wstandend(win); }
#undef wstandend
#define wstandend UNDEF(wstandend)
#endif

#ifdef wstandout
inline int UNDEF(wstandout)(WINDOW *win)  { return wstandout(win); }
#undef wstandout
#define wstandout UNDEF(wstandout)
#endif

/*
 *
 * C++ class for windows.
 *
 */

extern "C" int     _nc_ripoffline(int, int (*init)(WINDOW*, int));
extern "C" int     _nc_xx_ripoff_init(WINDOW *, int);
extern "C" int     _nc_has_mouse(void);

class NCURSES_CXX_IMPEXP NCursesWindow
{
  friend class NCursesMenu;
  friend class NCursesForm;

private:
  static bool    b_initialized;
  static void    initialize();
  void           constructing();
  friend int     _nc_xx_ripoff_init(WINDOW *, int);

  void           set_keyboard();

  NCURSES_COLOR_T getcolor(int getback) const;
  NCURSES_PAIRS_T getPair() const;

  static int     setpalette(NCURSES_COLOR_T fore, NCURSES_COLOR_T back, NCURSES_PAIRS_T pair);
  static int     colorInitialized;

  // This private constructor is only used during the initialization
  // of windows generated by ripoffline() calls.
  NCursesWindow(WINDOW* win, int ncols);

protected:
  virtual void   err_handler(const char *) const THROWS(NCursesException);
  // Signal an error with the given message text.

  static long count;        // count of all active windows:
  //   We rely on the c++ promise that
  //   all otherwise uninitialized
  //   static class vars are set to 0

  WINDOW*        w;                // the curses WINDOW

  bool           alloced;          // TRUE if we own the WINDOW

  NCursesWindow* par;              // parent, if subwindow
  NCursesWindow* subwins;          // head of subwindows list
  NCursesWindow* sib;              // next subwindow of parent

  void           kill_subwindows(); // disable all subwindows
  // Destroy all subwindows.

  /* Only for use by derived classes. They are then in charge to
     fill the member variables correctly. */
  NCursesWindow();

public:
  explicit NCursesWindow(WINDOW* window);   // useful only for stdscr

  NCursesWindow(int nlines,        // number of lines
		int ncols,         // number of columns
		int begin_y,       // line origin
		int begin_x);      // col origin

  NCursesWindow(NCursesWindow& par,// parent window
		int nlines,        // number of lines
		int ncols,         // number of columns
		int begin_y,       // absolute or relative
		int begin_x,       //   origins:
		char absrel = 'a');// if `a', begin_y & begin_x are
  // absolute screen pos, else if `r', they are relative to par origin

  NCursesWindow(NCursesWindow& par,// parent window
		bool do_box = TRUE);
  // this is the very common case that we want to create the subwindow that
  // is two lines and two columns smaller and begins at (1,1).
  // We may automatically request the box around it.

  NCursesWindow& operator=(const NCursesWindow& rhs)
  {
    if (this != &rhs)
      *this = rhs;
    return *this;
  }

  NCursesWindow(const NCursesWindow& rhs)
    : w(rhs.w), alloced(rhs.alloced), par(rhs.par), subwins(rhs.subwins), sib(rhs.sib)
  {
  }

  virtual ~NCursesWindow() THROWS(NCursesException);

  NCursesWindow Clone();
  // Make an exact copy of the window.

  // Initialization.
  static void    useColors(void);
  // Call this routine very early if you want to have colors.

  static int ripoffline(int ripoff_lines,
			int (*init)(NCursesWindow& win));
  // This function is used to generate a window of ripped-of lines.
  // If the argument is positive, lines are removed from the top, if it
  // is negative lines are removed from the bottom. This enhances the
  // lowlevel ripoffline() function because it uses the internal
  // implementation that allows to remove more than just a single line.
  // This function must be called before any other ncurses function. The
  // creation of the window is deferred until ncurses gets initialized.
  // The initialization function is then called.

  // -------------------------------------------------------------------------
  // terminal status
  // -------------------------------------------------------------------------
  int            lines() const { initialize(); return LINES; }
  // Number of lines on terminal, *not* window

  int            cols() const { initialize(); return COLS; }
  // Number of cols  on terminal, *not* window

  int            tabsize() const { initialize(); return TABSIZE; }
  // Size of a tab on terminal, *not* window

  static int     NumberOfColors();
  // Number of available colors

  int            colors() const { return NumberOfColors(); }
  // Number of available colors

  // -------------------------------------------------------------------------
  // window status
  // -------------------------------------------------------------------------
  int            height() const { return maxy() + 1; }
  // Number of lines in this window

  int            width() const { return maxx() + 1; }
  // Number of columns in this window

  int            begx() const { return getbegx(w); }
  // Column of top left corner relative to stdscr

  int            begy() const { return getbegy(w); }
  // Line of top left corner relative to stdscr

  int            curx() const { return getcurx(w); }
  // Column of top left corner relative to stdscr

  int            cury() const { return getcury(w); }
  // Line of top left corner relative to stdscr

  int            maxx() const { return getmaxx(w) == ERR ? ERR : getmaxx(w)-1; }
  // Largest x coord in window

  int            maxy() const { return getmaxy(w) == ERR ? ERR : getmaxy(w)-1; }
  // Largest y coord in window

  NCURSES_PAIRS_T getcolor() const;
  // Actual color pair

  NCURSES_COLOR_T foreground() const { return getcolor(0); }
  // Actual foreground color

  NCURSES_COLOR_T background() const { return getcolor(1); }
  // Actual background color

  int            setpalette(NCURSES_COLOR_T fore, NCURSES_COLOR_T back);
  // Set color palette entry

  int            setcolor(NCURSES_PAIRS_T pair);
  // Set actually used palette entry

  // -------------------------------------------------------------------------
  // window positioning
  // -------------------------------------------------------------------------
  virtual int    mvwin(int begin_y, int begin_x) {
    return ::mvwin(w, begin_y, begin_x); }
  // Move window to new position with the new position as top left corner.
  // This is virtual because it is redefined in NCursesPanel.

  // -------------------------------------------------------------------------
  // coordinate positioning
  // -------------------------------------------------------------------------
  int            move(int y, int x) { return ::wmove(w, y, x); }
  // Move cursor the this position

  void           getyx(int& y, int& x) const { ::getyx(w, y, x); }
  // Get current position of the cursor

  void           getbegyx(int& y, int& x) const { ::getbegyx(w, y, x); }
  // Get beginning of the window

  void           getmaxyx(int& y, int& x) const { ::getmaxyx(w, y, x); }
  // Get size of the window

  void           getparyx(int& y, int& x) const { ::getparyx(w, y, x); }
  // Get parent's beginning of the window

  int            mvcur(int oldrow, int oldcol, int newrow, int newcol) const {
    return ::mvcur(oldrow, oldcol, newrow, newcol); }
  // Perform lowlevel cursor motion that takes effect immediately.

  // -------------------------------------------------------------------------
  // input
  // -------------------------------------------------------------------------
  int            getch() { return ::wgetch(w); }
  // Get a keystroke from the window.

  int            getch(int y, int x) { return ::mvwgetch(w, y, x); }
  // Move cursor to position and get a keystroke from the window

  int            getstr(char* str, int n=-1) {
    return ::wgetnstr(w, str, n); }
  // Read a series of characters into str until a newline or carriage return
  // is received. Read at most n characters. If n is negative, the limit is
  // ignored.

  int            getstr(int y, int x, char* str, int n=-1) {
    return ::mvwgetnstr(w, y, x, str, n); }
  // Move the cursor to the requested position and then perform the getstr()
  // as described above.

  int            instr(char *s, int n=-1) { return ::winnstr(w, s, n); }
  // Get a string of characters from the window into the buffer s. Retrieve
  // at most n characters, if n is negative retrieve all characters up to the
  // end of the current line. Attributes are stripped from the characters.

  int            instr(int y, int x, char *s, int n=-1) {
    return ::mvwinnstr(w, y, x, s, n); }
  // Move the cursor to the requested position and then perform the instr()
  // as described above.

  int            scanw(const char* fmt, ...)
    // Perform a scanw function from the window.
#if __GNUG__ >= 2
    __attribute__ ((format (scanf, 2, 3)));
#else
  ;
#endif

  int            scanw(const char*, va_list);
    // Perform a scanw function from the window.

  int            scanw(int y, int x, const char* fmt, ...)
    // Move the cursor to the requested position and then perform a scanw
    // from the window.
#if __GNUG__ >= 2
    __attribute__ ((format (scanf, 4, 5)));
#else
  ;
#endif

  int            scanw(int y, int x, const char* fmt, va_list);
    // Move the cursor to the requested position and then perform a scanw
    // from the window.

  // -------------------------------------------------------------------------
  // output
  // -------------------------------------------------------------------------
  int            addch(const chtype ch) { return ::waddch(w, ch); }
  // Put attributed character to the window.

  int            addch(int y, int x, const chtype ch) {
    return ::mvwaddch(w, y, x, ch); }
  // Move cursor to the requested position and then put attributed character
  // to the window.

  int            echochar(const chtype ch) { return ::wechochar(w, ch); }
  // Put attributed character to the window and refresh it immediately.

  int            addstr(const char* str, int n=-1) {
    return ::waddnstr(w, str, n); }
  // Write the string str to the window, stop writing if the terminating
  // NUL or the limit n is reached. If n is negative, it is ignored.

  int            addstr(int y, int x, const char * str, int n=-1) {
    return ::mvwaddnstr(w, y, x, str, n); }
  // Move the cursor to the requested position and then perform the addchstr
  // as described above.

  int            addchstr(const chtype* str, int n=-1) {
    return ::waddchnstr(w, str, n); }
  // Write the string str to the window, stop writing if the terminating
  // NUL or the limit n is reached. If n is negative, it is ignored.

  int            addchstr(int y, int x, const chtype * str, int n=-1) {
    return ::mvwaddchnstr(w, y, x, str, n); }
  // Move the cursor to the requested position and then perform the addchstr
  // as described above.

  int            printw(const char* fmt, ...)
    // Do a formatted print to the window.
#if (__GNUG__ >= 2) && !defined(printf)
    __attribute__ ((format (printf, 2, 3)));
#else
  ;
#endif

  int            printw(int y, int x, const char * fmt, ...)
    // Move the cursor and then do a formatted print to the window.
#if (__GNUG__ >= 2) && !defined(printf)
    __attribute__ ((format (printf, 4, 5)));
#else
  ;
#endif

  int            printw(const char* fmt, va_list args);
    // Do a formatted print to the window.

  int            printw(int y, int x, const char * fmt, va_list args);
    // Move the cursor and then do a formatted print to the window.

  chtype         inch() const { return ::winch(w); }
  // Retrieve attributed character under the current cursor position.

  chtype         inch(int y, int x) { return ::mvwinch(w, y, x); }
  // Move cursor to requested position and then retrieve attributed character
  // at this position.

  int            inchstr(chtype* str, int n=-1) {
    return ::winchnstr(w, str, n); }
  // Read the string str from the window, stop reading if the terminating
  // NUL or the limit n is reached. If n is negative, it is ignored.

  int            inchstr(int y, int x, chtype * str, int n=-1) {
    return ::mvwinchnstr(w, y, x, str, n); }
  // Move the cursor to the requested position and then perform the inchstr
  // as described above.

  int            insch(chtype ch) { return ::winsch(w, ch); }
  // Insert attributed character into the window before current cursor
  // position.

  int            insch(int y, int x, chtype ch) {
    return ::mvwinsch(w, y, x, ch); }
  // Move cursor to requested position and then insert the attributed
  // character before that position.

  int            insertln() { return ::winsdelln(w, 1); }
  // Insert an empty line above the current line.

  int            insdelln(int n=1) { return ::winsdelln(w, n); }
  // If n>0 insert that many lines above the current line. If n<0 delete
  // that many lines beginning with the current line.

  int            insstr(const char *s, int n=-1) {
    return ::winsnstr(w, s, n); }
  // Insert the string into the window before the current cursor position.
  // Insert stops at end of string or when the limit n is reached. If n is
  // negative, it is ignored.

  int            insstr(int y, int x, const char *s, int n=-1) {
    return ::mvwinsnstr(w, y, x, s, n); }
  // Move the cursor to the requested position and then perform the insstr()
  // as described above.

  int            attron (chtype at) { return ::wattron (w, at); }
  // Switch on the window attributes;

  int            attroff(chtype at) { return ::wattroff(w, static_cast<int>(at)); }
  // Switch off the window attributes;

  int            attrset(chtype at) { return ::wattrset(w, static_cast<int>(at)); }
  // Set the window attributes;

  chtype         attrget() { return ::getattrs(w); }
  // Get the window attributes;

  int            color_set(NCURSES_PAIRS_T color_pair_number, void* opts=NULL) {
    return ::wcolor_set(w, color_pair_number, opts); }
  // Set the window color attribute;

  int            chgat(int n, attr_t attr, NCURSES_PAIRS_T color, const void *opts=NULL) {
    return ::wchgat(w, n, attr, color, opts); }
  // Change the attributes of the next n characters in the current line. If
  // n is negative or greater than the number of remaining characters in the
  // line, the attributes will be changed up to the end of the line.

  int            chgat(int y, int x,
		       int n, attr_t attr, NCURSES_PAIRS_T color, const void *opts=NULL) {
    return ::mvwchgat(w, y, x, n, attr, color, opts); }
  // Move the cursor to the requested position and then perform chgat() as
  // described above.

  // -------------------------------------------------------------------------
  // background
  // -------------------------------------------------------------------------
  chtype         getbkgd() const { return ::getbkgd(w); }
  // Get current background setting.

  int            bkgd(const chtype ch) { return ::wbkgd(w, ch); }
  // Set the background property and apply it to the window.

  void           bkgdset(chtype ch) { ::wbkgdset(w, ch); }
  // Set the background property.

  // -------------------------------------------------------------------------
  // borders
  // -------------------------------------------------------------------------
  int            box(chtype vert=0, chtype  hor=0) {
    return ::wborder(w, vert, vert, hor, hor, 0, 0, 0, 0); }
  // Draw a box around the window with the given vertical and horizontal
  // drawing characters. If you specify a zero as character, curses will try
  // to find a "nice" character.

  int            border(chtype left=0, chtype right=0,
			chtype top =0, chtype bottom=0,
			chtype top_left =0, chtype top_right=0,
			chtype bottom_left =0, chtype bottom_right=0) {
    return ::wborder(w, left, right, top, bottom, top_left, top_right,
		     bottom_left, bottom_right); }
  // Draw a border around the window with the given characters for the
  // various parts of the border. If you pass zero for a character, curses
  // will try to find "nice" characters.

  // -------------------------------------------------------------------------
  // lines and boxes
  // -------------------------------------------------------------------------
  int            hline(int len, chtype ch=0) { return ::whline(w, ch, len); }
  // Draw a horizontal line of len characters with the given character. If
  // you pass zero for the character, curses will try to find a "nice" one.

  int            hline(int y, int x, int len, chtype ch=0) {
    return ::mvwhline(w, y, x, ch, len); }
  // Move the cursor to the requested position and then draw a horizontal line.

  int            vline(int len, chtype ch=0) { return ::wvline(w, ch, len); }
  // Draw a vertical line of len characters with the given character. If
  // you pass zero for the character, curses will try to find a "nice" one.

  int            vline(int y, int x, int len, chtype ch=0) {
    return ::mvwvline(w, y, x, ch, len); }
  // Move the cursor to the requested position and then draw a vertical line.

  // -------------------------------------------------------------------------
  // erasure
  // -------------------------------------------------------------------------
  int            erase() { return ::werase(w); }
  // Erase the window.

  int            clear() { return ::wclear(w); }
  // Clear the window.

  int            clearok(bool bf) { return ::clearok(w, bf); }
  // Set/Reset the clear flag. If set, the next refresh() will clear the
  // screen.

  int            clrtobot() { return ::wclrtobot(w); }
  // Clear to the end of the window.

  int            clrtoeol() { return ::wclrtoeol(w); }
  // Clear to the end of the line.

  int            delch() { return ::wdelch(w); }
  // Delete character under the cursor.

  int            delch(int y, int x) { return ::mvwdelch(w, y, x); }
  // Move cursor to requested position and delete the character under the
  // cursor.

  int            deleteln() { return ::winsdelln(w, -1); }
  // Delete the current line.

  // -------------------------------------------------------------------------
  // screen control
  // -------------------------------------------------------------------------
  int            scroll(int amount=1) { return ::wscrl(w, amount); }
  // Scroll amount lines. If amount is positive, scroll up, otherwise
  // scroll down.

  int            scrollok(bool bf) { return ::scrollok(w, bf); }
  // If bf is TRUE, window scrolls if cursor is moved off the bottom
  // edge of the window or a scrolling region, otherwise the cursor is left
  // at the bottom line.

  int            setscrreg(int from, int to) {
    return ::wsetscrreg(w, from, to); }
  // Define a soft scrolling region.

  int            idlok(bool bf) { return ::idlok(w, bf); }
  // If bf is TRUE, use insert/delete line hardware support if possible.
  // Otherwise do it in software.

  void           idcok(bool bf) { ::idcok(w, bf); }
  // If bf is TRUE, use insert/delete character hardware support if possible.
  // Otherwise do it in software.

  int            touchline(int s, int c) { return ::touchline(w, s, c); }
  // Mark the given lines as modified.

  int            touchwin()   { return ::wtouchln(w, 0, height(), 1); }
  // Mark the whole window as modified.

  int            untouchwin() { return ::wtouchln(w, 0, height(), 0); }
  // Mark the whole window as unmodified.

  int            touchln(int s, int cnt, bool changed=TRUE) {
    return ::wtouchln(w, s, cnt, static_cast<int>(changed ? 1 : 0)); }
  // Mark cnt lines beginning from line s as changed or unchanged, depending
  // on the value of the changed flag.

  bool           is_linetouched(int line) const {
    return (::is_linetouched(w, line) == TRUE ? TRUE:FALSE); }
  // Return TRUE if line is marked as changed, FALSE otherwise

  bool           is_wintouched() const {
    return (::is_wintouched(w) ? TRUE:FALSE); }
  // Return TRUE if window is marked as changed, FALSE otherwise

  int            leaveok(bool bf) { return ::leaveok(w, bf); }
  // If bf is TRUE, curses will leave the cursor after an update wherever
  // it is after the update.

  int            redrawln(int from, int n) { return ::wredrawln(w, from, n); }
  // Redraw n lines starting from the requested line

  int            redrawwin() { return ::wredrawln(w, 0, height()); }
  // Redraw the whole window

  int            doupdate()  { return ::doupdate(); }
  // Do all outputs to make the physical screen looking like the virtual one

  void           syncdown()  { ::wsyncdown(w); }
  // Propagate the changes down to all descendant windows

  void           syncup()    { ::wsyncup(w); }
  // Propagate the changes up in the hierarchy

  void           cursyncup() { ::wcursyncup(w); }
  // Position the cursor in all ancestor windows corresponding to our setting

  int            syncok(bool bf) { return ::syncok(w, bf); }
  // If called with bf=TRUE, syncup() is called whenever the window is changed

#ifndef _no_flushok
  int            flushok(bool bf) { return ::flushok(w, bf); }
#endif

  void           immedok(bool bf) { ::immedok(w, bf); }
  // If called with bf=TRUE, any change in the window will cause an
  // automatic immediate refresh()

  int            intrflush(bool bf) { return ::intrflush(w, bf); }

  int            keypad(bool bf) { return ::keypad(w, bf); }
  // If called with bf=TRUE, the application will interpret function keys.

  int            nodelay(bool bf) { return ::nodelay(w, bf); }

  int            meta(bool bf) { return ::meta(w, bf); }
  // If called with bf=TRUE, keys may generate 8-Bit characters. Otherwise
  // 7-Bit characters are generated.

  int            standout() { return ::wstandout(w); }
  // Enable "standout" attributes

  int            standend() { return ::wstandend(w); }
  // Disable "standout" attributes

  // -------------------------------------------------------------------------
  // The next two are virtual, because we redefine them in the
  // NCursesPanel class.
  // -------------------------------------------------------------------------
  virtual int    refresh() { return ::wrefresh(w); }
  // Propagate the changes in this window to the virtual screen and call
  // doupdate(). This is redefined in NCursesPanel.

  virtual int    noutrefresh() { return ::wnoutrefresh(w); }
  // Propagate the changes in this window to the virtual screen. This is
  // redefined in NCursesPanel.

  // -------------------------------------------------------------------------
  // multiple window control
  // -------------------------------------------------------------------------
  int            overlay(NCursesWindow& win) {
    return ::overlay(w, win.w); }
  // Overlay this window over win.

  int            overwrite(NCursesWindow& win) {
    return ::overwrite(w, win.w); }
  // Overwrite win with this window.

  int            copywin(NCursesWindow& win,
			 int sminrow, int smincol,
			 int dminrow, int dmincol,
			 int dmaxrow, int dmaxcol, bool overlaywin=TRUE) {
    return ::copywin(w, win.w, sminrow, smincol, dminrow, dmincol,
		     dmaxrow, dmaxcol, static_cast<int>(overlaywin ? 1 : 0)); }
  // Overlay or overwrite the rectangle in win given by dminrow,dmincol,
  // dmaxrow,dmaxcol with the rectangle in this window beginning at
  // sminrow,smincol.

  // -------------------------------------------------------------------------
  // Extended functions
  // -------------------------------------------------------------------------
#if defined(NCURSES_EXT_FUNCS) && (NCURSES_EXT_FUNCS != 0)
  int            wresize(int newLines, int newColumns) {
    return ::wresize(w, newLines, newColumns); }
#endif

  // -------------------------------------------------------------------------
  // Mouse related
  // -------------------------------------------------------------------------
  bool has_mouse() const;
  // Return TRUE if terminal supports a mouse, FALSE otherwise

  // -------------------------------------------------------------------------
  // traversal support
  // -------------------------------------------------------------------------
  NCursesWindow*  child() { return subwins; }
  // Get the first child window.

  NCursesWindow*  sibling() { return sib; }
  // Get the next child of my parent.

  NCursesWindow*  parent() { return par; }
  // Get my parent.

  bool isDescendant(NCursesWindow& win);
  // Return TRUE if win is a descendant of this.
};

// -------------------------------------------------------------------------
// We leave this here for compatibility reasons.
// -------------------------------------------------------------------------
class NCURSES_CXX_IMPEXP NCursesColorWindow : public NCursesWindow
{
public:
  explicit NCursesColorWindow(WINDOW* &window)   // useful only for stdscr
    : NCursesWindow(window) {
      useColors(); }

  NCursesColorWindow(int nlines,        // number of lines
		     int ncols,         // number of columns
		     int begin_y,       // line origin
		     int begin_x)       // col origin
    : NCursesWindow(nlines, ncols, begin_y, begin_x) {
      useColors(); }

  NCursesColorWindow(NCursesWindow& parentWin,// parent window
		     int nlines,        // number of lines
		     int ncols,         // number of columns
		     int begin_y,       // absolute or relative
		     int begin_x,       //   origins:
		     char absrel = 'a') // if `a', by & bx are
    : NCursesWindow(parentWin,
		    nlines, ncols,	// absolute screen pos,
		    begin_y, begin_x,   // else if `r', they are
		    absrel ) {          // relative to par origin
      useColors(); }
};

// These enum definitions really belong inside the NCursesPad class, but only
// recent compilers support that feature.

  typedef enum {
    REQ_PAD_REFRESH = KEY_MAX + 1,
    REQ_PAD_UP,
    REQ_PAD_DOWN,
    REQ_PAD_LEFT,
    REQ_PAD_RIGHT,
    REQ_PAD_EXIT
  } Pad_Request;

  const Pad_Request PAD_LOW  = REQ_PAD_REFRESH;   // lowest  op-code
  const Pad_Request PAD_HIGH = REQ_PAD_EXIT;      // highest op-code

// -------------------------------------------------------------------------
// Pad Support. We allow an association of a pad with a "real" window
// through which the pad may be viewed.
// -------------------------------------------------------------------------
class NCURSES_CXX_IMPEXP NCursesPad : public NCursesWindow
{
private:
  NCursesWindow* viewWin;       // the "viewport" window
  NCursesWindow* viewSub;       // the "viewport" subwindow

  int h_gridsize, v_gridsize;

protected:
  int min_row, min_col;         // top left row/col of the pads display area

  NCursesWindow* Win(void) const {
    // Get the window into which the pad should be copied (if any)
    return (viewSub?viewSub:(viewWin?viewWin:0));
  }

  NCursesWindow* getWindow(void) const {
    return viewWin;
  }

  NCursesWindow* getSubWindow(void) const {
    return viewSub;
  }

  virtual int driver (int key);      // Virtualize keystroke key
  // The driver translates the keystroke c into an Pad_Request

  virtual void OnUnknownOperation(int pad_req) {
    (void) pad_req;
    ::beep();
  }
  // This is called if the driver returns an unknown op-code

  virtual void OnNavigationError(int pad_req) {
    (void) pad_req;
    ::beep();
  }
  // This is called if a navigation request couldn't be satisfied

  virtual void OnOperation(int pad_req) {
    (void) pad_req;
  };
  // OnOperation is called if a Pad_Operation was executed and just before
  // the refresh() operation is done.

public:
  NCursesPad(int nlines, int ncols);
  // create a pad with the given size

  NCursesPad& operator=(const NCursesPad& rhs)
  {
    if (this != &rhs) {
      *this = rhs;
      NCursesWindow::operator=(rhs);
    }
    return *this;
  }

  NCursesPad(const NCursesPad& rhs)
    : NCursesWindow(rhs),
      viewWin(rhs.viewWin),
      viewSub(rhs.viewSub),
      h_gridsize(rhs.h_gridsize),
      v_gridsize(rhs.v_gridsize),
      min_row(rhs.min_row),
      min_col(rhs.min_col)
  {
  }

  virtual ~NCursesPad() THROWS(NCursesException) {}

  int echochar(const chtype ch) { return ::pechochar(w, ch); }
  // Put the attributed character onto the pad and immediately do a
  // prefresh().

  int refresh() NCURSES_OVERRIDE;
  // If a viewport is defined the pad is displayed in this window, otherwise
  // this is a noop.

  int refresh(int pminrow, int pmincol,
	      int sminrow, int smincol,
	      int smaxrow, int smaxcol) {
    return ::prefresh(w, pminrow, pmincol,
		      sminrow, smincol, smaxrow, smaxcol);
  }
  // The coordinates sminrow,smincol,smaxrow,smaxcol describe a rectangle
  // on the screen. <b>refresh</b> copies a rectangle of this size beginning
  // with top left corner pminrow,pmincol onto the screen and calls doupdate().

  int noutrefresh() NCURSES_OVERRIDE;
  // If a viewport is defined the pad is displayed in this window, otherwise
  // this is a noop.

  int noutrefresh(int pminrow, int pmincol,
		  int sminrow, int smincol,
		  int smaxrow, int smaxcol) {
    return ::pnoutrefresh(w, pminrow, pmincol,
			  sminrow, smincol, smaxrow, smaxcol);
  }
  // Does the same as refresh() but without calling doupdate().

  virtual void setWindow(NCursesWindow& view, int v_grid = 1, int h_grid = 1);
  // Add the window "view" as viewing window to the pad.

  virtual void setSubWindow(NCursesWindow& sub);
  // Use the subwindow "sub" of the viewport window for the actual viewing.
  // The full viewport window is usually used to provide some decorations
  // like frames, titles etc.

  virtual void operator() (void);
  // Perform Pad's operation
};

// A FramedPad is constructed always with a viewport window. This viewport
// will be framed (by a box() command) and the interior of the box is the
// viewport subwindow. On the frame we display scrollbar sliders.
class NCURSES_CXX_IMPEXP NCursesFramedPad : public NCursesPad
{
protected:
  virtual void OnOperation(int pad_req) NCURSES_OVERRIDE;

public:
  NCursesFramedPad(NCursesWindow& win, int nlines, int ncols,
		   int v_grid = 1, int h_grid = 1)
    : NCursesPad(nlines, ncols) {
    NCursesPad::setWindow(win, v_grid, h_grid);
    NCursesPad::setSubWindow(*(new NCursesWindow(win)));
  }
  // Construct the FramedPad with the given Window win as viewport.

  virtual ~NCursesFramedPad() THROWS(NCursesException) {
    delete getSubWindow();
  }

  void setWindow(NCursesWindow& view, int v_grid = 1, int h_grid = 1) NCURSES_OVERRIDE {
    (void) view;
    (void) v_grid;
    (void) h_grid;
    err_handler("Operation not allowed");
  }
  // Disable this call; the viewport is already defined

  void setSubWindow(NCursesWindow& sub) NCURSES_OVERRIDE {
    (void) sub;
    err_handler("Operation not allowed");
  }
  // Disable this call; the viewport subwindow is already defined

};

#endif /* NCURSES_CURSESW_H_incl */
