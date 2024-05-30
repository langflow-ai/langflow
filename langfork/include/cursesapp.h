// * This makes emacs happy -*-Mode: C++;-*-
/****************************************************************************
 * Copyright 2019-2020,2021 Thomas E. Dickey                                *
 * Copyright 1998-2005,2011 Free Software Foundation, Inc.                  *
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

// $Id: cursesapp.h,v 1.18 2021/06/17 21:26:02 tom Exp $

#ifndef NCURSES_CURSESAPP_H_incl
#define NCURSES_CURSESAPP_H_incl

#include <ncursesw/cursslk.h>

#if (defined(_WIN32) || defined(_WIN64))
# define NCURSES_CXX_MAIN_NAME cursespp_main
# define NCURSES_CXX_MAIN \
  int main(int argc, char *argv[]) { \
  	return NCURSES_CXX_MAIN_NAME(argc, argv); \
  }
#else
# define NCURSES_CXX_MAIN_NAME main
#endif
NCURSES_CXX_IMPEXP int NCURSES_CXX_MAIN_NAME(int argc, char *argv[]);

class NCURSES_CXX_IMPEXP NCursesApplication {
public:
  typedef struct _slk_link {          // This structure is used to maintain
    struct _slk_link* prev;           // a stack of SLKs
    Soft_Label_Key_Set* SLKs;
  } SLK_Link;
private:
  static int rinit(NCursesWindow& w); // Internal Init function for title
  static NCursesApplication* theApp;  // Global ref. to the application

  static SLK_Link* slk_stack;

protected:
  static NCursesWindow* titleWindow;  // The Title Window (if any)

  bool b_Colors;                      // Is this a color application?
  NCursesWindow* Root_Window;         // This is the stdscr equiv.

  // Initialization of attributes;
  // Rewrite this in your derived class if you prefer other settings
  virtual void init(bool bColors);

  // The number of lines for the title window. Default is no title window
  // You may rewrite this in your derived class
  virtual int titlesize() const {
    return 0;
  }

  // This method is called to put something into the title window initially
  // You may rewrite this in your derived class
  virtual void title() {
  }

  // The layout used for the Soft Label Keys. Default is to have no SLKs.
  // You may rewrite this in your derived class
  virtual Soft_Label_Key_Set::Label_Layout useSLKs() const {
    return Soft_Label_Key_Set::None;
  }

  // This method is called to initialize the SLKs. Default is nothing.
  // You may rewrite this in your derived class
  virtual void init_labels(Soft_Label_Key_Set& S) const {
    (void) S;
  }

  // Your derived class must implement this method. The return value must
  // be the exit value of your application.
  virtual int run() = 0;

  // The constructor is protected, so you may use it in your derived
  // class constructor. The argument tells whether or not you want colors.
  NCursesApplication(bool wantColors = FALSE);

  NCursesApplication& operator=(const NCursesApplication& rhs)
  {
    if (this != &rhs) {
      *this = rhs;
    }
    return *this;
  }

  NCursesApplication(const NCursesApplication& rhs)
    : b_Colors(rhs.b_Colors),
      Root_Window(rhs.Root_Window)
  {
  }

  static NCursesWindow *&getTitleWindow();

public:
  virtual ~NCursesApplication() THROWS(NCursesException);

  // Get a pointer to the current application object
  static NCursesApplication* getApplication();

  // This method runs the application and returns its exit value
  int operator()(void);

  // Process the commandline arguments. The default implementation simply
  // ignores them. Your derived class may rewrite this.
  virtual void handleArgs(int argc, char* argv[]) {
    (void) argc;
    (void) argv;
  }

  // Does this application use colors?
  inline bool useColors() const {
    return b_Colors;
  }

  // Push the Key Set S onto the SLK Stack. S then becomes the current set
  // of Soft Labelled Keys.
  void push(Soft_Label_Key_Set& S);

  // Throw away the current set of SLKs and make the previous one the
  // new current set.
  bool pop();

  // Retrieve the current set of Soft Labelled Keys.
  Soft_Label_Key_Set* top() const;

  // Attributes to use for menu and forms foregrounds
  virtual chtype foregrounds() const {
    return b_Colors ? static_cast<chtype>(COLOR_PAIR(1)) : A_BOLD;
  }

  // Attributes to use for menu and forms backgrounds
  virtual chtype backgrounds() const {
    return b_Colors ? static_cast<chtype>(COLOR_PAIR(2)) : A_NORMAL;
  }

  // Attributes to use for inactive (menu) elements
  virtual chtype inactives() const {
    return b_Colors ? static_cast<chtype>(COLOR_PAIR(3)|A_DIM) : A_DIM;
  }

  // Attributes to use for (form) labels and SLKs
  virtual chtype labels() const {
    return b_Colors ? static_cast<chtype>(COLOR_PAIR(4)) : A_NORMAL;
  }

  // Attributes to use for form backgrounds
  virtual chtype dialog_backgrounds() const {
    return b_Colors ? static_cast<chtype>(COLOR_PAIR(4)) : A_NORMAL;
  }

  // Attributes to use as default for (form) window backgrounds
  virtual chtype window_backgrounds() const {
    return b_Colors ? static_cast<chtype>(COLOR_PAIR(5)) : A_NORMAL;
  }

  // Attributes to use for the title window
  virtual chtype screen_titles() const {
    return b_Colors ? static_cast<chtype>(COLOR_PAIR(6)) : A_BOLD;
  }

};

#endif /* NCURSES_CURSESAPP_H_incl */
