// * This makes emacs happy -*-Mode: C++;-*-
// vile:cppmode
/****************************************************************************
 * Copyright 2019-2021,2022 Thomas E. Dickey                                *
 * Copyright 1998-2012,2014 Free Software Foundation, Inc.                  *
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

/****************************************************************************
 *   Author: Juergen Pfeifer, 1997                                          *
 ****************************************************************************/

#ifndef NCURSES_CURSESP_H_incl
#define NCURSES_CURSESP_H_incl 1

// $Id: cursesp.h,v 1.36 2022/08/20 20:52:15 tom Exp $

#include <ncursesw/cursesw.h>

extern "C" {
#  include <ncursesw/panel.h>
}

class NCURSES_CXX_IMPEXP NCursesPanel
  : public NCursesWindow
{
protected:
  PANEL *p;
  static NCursesPanel *dummy;

private:
  // This structure is used for the panel's user data field to link the
  // PANEL* to the C++ object and to provide extra space for a user pointer.
  typedef struct {
    void*               m_user;      // the pointer for the user's data
    const NCursesPanel* m_back;      // backward pointer to C++ object
    const PANEL*        m_owner;     // the panel itself
  } UserHook;

  inline UserHook *UserPointer()
  {
    UserHook* uptr = reinterpret_cast<UserHook*>(
                           const_cast<void *>(::panel_userptr (p)));
    return uptr;
  }

  void init();                       // Initialize the panel object

protected:
  void set_user(void *user)
  {
    UserHook* uptr = UserPointer();
    if (uptr != 0 && uptr->m_back==this && uptr->m_owner==p) {
      uptr->m_user = user;
    }
  }
  // Set the user pointer of the panel.

  void *get_user()
  {
    UserHook* uptr = UserPointer();
    void *result = 0;
    if (uptr != 0 && uptr->m_back==this && uptr->m_owner==p)
      result = uptr->m_user;
    return result;
  }

  void OnError (int err) const THROW2(NCursesException const, NCursesPanelException)
  {
    if (err==ERR)
      THROW(new NCursesPanelException (this, err));
  }
  // If err is equal to the curses error indicator ERR, an error handler
  // is called.

  // Get a keystroke. Default implementation calls getch()
  virtual int getKey(void);

public:
  NCursesPanel(int nlines,
	       int ncols,
	       int begin_y = 0,
	       int begin_x = 0)
    : NCursesWindow(nlines,ncols,begin_y,begin_x), p(0)
  {
    init();
  }
  // Create a panel with this size starting at the requested position.

  NCursesPanel()
    : NCursesWindow(::stdscr), p(0)
  {
    init();
  }
  // This constructor creates the default Panel associated with the
  // ::stdscr window

  NCursesPanel& operator=(const NCursesPanel& rhs)
  {
    if (this != &rhs) {
      *this = rhs;
      NCursesWindow::operator=(rhs);
    }
    return *this;
  }

  NCursesPanel(const NCursesPanel& rhs)
    : NCursesWindow(rhs),
      p(rhs.p)
  {
  }

  virtual ~NCursesPanel() THROWS(NCursesException);

  // basic manipulation
  inline void hide()
  {
    OnError (::hide_panel(p));
  }
  // Hide the panel. It stays in the stack but becomes invisible.

  inline void show()
  {
    OnError (::show_panel(p));
  }
  // Show the panel, i.e. make it visible.

  inline void top()
  {
    OnError (::top_panel(p));
  }
  // Make this panel the top panel in the stack.

  inline void bottom()
  {
    OnError (::bottom_panel(p));
  }
  // Make this panel the bottom panel in the stack.
  // N.B.: The panel associated with ::stdscr is always on the bottom. So
  // actually bottom() makes the panel the first above ::stdscr.

  virtual int mvwin(int y, int x) NCURSES_OVERRIDE
  {
    OnError(::move_panel(p, y, x));
    return OK;
  }

  inline bool hidden() const
  {
    return (::panel_hidden (p) ? TRUE : FALSE);
  }
  // Return TRUE if the panel is hidden, FALSE otherwise.

/* The functions panel_above() and panel_below() are not reflected in
   the NCursesPanel class. The reason for this is, that we cannot
   assume that a panel retrieved by those operations is one wrapped
   by a C++ class. Although this situation might be handled, we also
   need a reverse mapping from PANEL to NCursesPanel which needs some
   redesign of the low level stuff. At the moment, we define them in the
   interface but they will always produce an error. */
  inline NCursesPanel& above() const
  {
    OnError(ERR);
    return *dummy;
  }

  inline NCursesPanel& below() const
  {
    OnError(ERR);
    return *dummy;
  }

  // Those two are rewrites of the corresponding virtual members of
  // NCursesWindow
  virtual int refresh() NCURSES_OVERRIDE;
  // Propagate all panel changes to the virtual screen and update the
  // physical screen.

  virtual int noutrefresh() NCURSES_OVERRIDE;
  // Propagate all panel changes to the virtual screen.

  static void redraw();
  // Redraw all panels.

  // decorations
  virtual void frame(const char* title=NULL,
		     const char* btitle=NULL);
  // Put a frame around the panel and put the title centered in the top line
  // and btitle in the bottom line.

  virtual void boldframe(const char* title=NULL,
			 const char* btitle=NULL);
  // Same as frame(), but use highlighted attributes.

  virtual void label(const char* topLabel,
		     const char* bottomLabel);
  // Put the title centered in the top line and btitle in the bottom line.

  virtual void centertext(int row,const char* label);
  // Put the label text centered in the specified row.
};

/* We use templates to provide a typesafe mechanism to associate
 * user data with a panel. A NCursesUserPanel<T> is a panel
 * associated with some user data of type T.
 */
template<class T> class NCursesUserPanel : public NCursesPanel
{
public:
  NCursesUserPanel (int nlines,
		    int ncols,
		    int begin_y = 0,
		    int begin_x = 0,
		    const T* p_UserData = STATIC_CAST(T*)(0))
    : NCursesPanel (nlines, ncols, begin_y, begin_x)
  {
      if (p)
	set_user (const_cast<void *>(reinterpret_cast<const void*>
				     (p_UserData)));
  };
  // This creates an user panel of the requested size with associated
  // user data pointed to by p_UserData.

  explicit NCursesUserPanel(const T* p_UserData = STATIC_CAST(T*)(0)) : NCursesPanel()
  {
    if (p)
      set_user(const_cast<void *>(reinterpret_cast<const void*>(p_UserData)));
  };
  // This creates an user panel associated with the ::stdscr and user data
  // pointed to by p_UserData.

  virtual ~NCursesUserPanel() THROWS(NCursesException) {};

  T* UserData (void)
  {
    return reinterpret_cast<T*>(get_user ());
  };
  // Retrieve the user data associated with the panel.

  virtual void setUserData (const T* p_UserData)
  {
    if (p)
      set_user (const_cast<void *>(reinterpret_cast<const void*>(p_UserData)));
  }
  // Associate the user panel with the user data pointed to by p_UserData.
};

#endif /* NCURSES_CURSESP_H_incl */
