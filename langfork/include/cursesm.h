// * This makes emacs happy -*-Mode: C++;-*-
/****************************************************************************
 * Copyright 2019-2020,2022 Thomas E. Dickey                                *
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

// $Id: cursesm.h,v 1.35 2022/08/20 20:52:15 tom Exp $

#ifndef NCURSES_CURSESM_H_incl
#define NCURSES_CURSESM_H_incl 1

#include <ncursesw/cursesp.h>

extern "C" {
#  include <ncursesw/menu.h>
}
//
// -------------------------------------------------------------------------
// This wraps the ITEM type of <ncursesw/menu.h>
// -------------------------------------------------------------------------
//
class NCURSES_CXX_IMPEXP NCursesMenuItem
{
  friend class NCursesMenu;

protected:
  ITEM *item;

  inline void OnError (int err) const THROW2(NCursesException const, NCursesMenuException) {
    if (err != E_OK)
      THROW(new NCursesMenuException (err));
  }

public:
  NCursesMenuItem (const char* p_name     = NULL,
		   const char* p_descript = NULL)
    : item(0)
  {
    item = p_name ? ::new_item (p_name, p_descript) : STATIC_CAST(ITEM*)(0);
    if (p_name && !item)
      OnError (E_SYSTEM_ERROR);
  }
  // Create an item. If you pass both parameters as NULL, a delimiting
  // item is constructed which can be used to terminate a list of
  // NCursesMenu objects.

  NCursesMenuItem& operator=(const NCursesMenuItem& rhs)
  {
    if (this != &rhs) {
      *this = rhs;
    }
    return *this;
  }

  NCursesMenuItem(const NCursesMenuItem& rhs)
    : item(0)
  {
    (void) rhs;
  }

  virtual ~NCursesMenuItem () THROWS(NCursesException);
  // Release the items memory

  inline const char* name () const {
    return ::item_name (item);
  }
  // Name of the item

  inline const char* description () const {
    return ::item_description (item);
  }
  // Description of the item

  inline int (index) (void) const {
    return ::item_index (item);
  }
  // Index of the item in an item array (or -1)

  inline void options_on (Item_Options opts) {
    OnError (::item_opts_on (item, opts));
  }
  // Switch on the items options

  inline void options_off (Item_Options opts) {
    OnError (::item_opts_off (item, opts));
  }
  // Switch off the item's option

  inline Item_Options options () const {
    return ::item_opts (item);
  }
  // Retrieve the items options

  inline void set_options (Item_Options opts) {
    OnError (::set_item_opts (item, opts));
  }
  // Set the items options

  inline void set_value (bool f) {
    OnError (::set_item_value (item,f));
  }
  // Set/Reset the items selection state

  inline bool value () const {
    return ::item_value (item);
  }
  // Retrieve the items selection state

  inline bool visible () const {
    return ::item_visible (item);
  }
  // Retrieve visibility of the item

  virtual bool action();
  // Perform an action associated with this item; you may use this in an
  // user supplied driver for a menu; you may derive from this class and
  // overload action() to supply items with different actions.
  // If an action returns true, the menu will be exited. The default action
  // is to do nothing.
};

// Prototype for an items callback function.
typedef bool ITEMCALLBACK(NCursesMenuItem&);

// If you don't like to create a child class for individual items to
// overload action(), you may use this class and provide a callback
// function pointer for items.
class NCURSES_CXX_IMPEXP NCursesMenuCallbackItem : public NCursesMenuItem
{
private:
  ITEMCALLBACK* p_fct;

public:
  NCursesMenuCallbackItem(ITEMCALLBACK* fct       = NULL,
			  const char* p_name      = NULL,
			  const char* p_descript  = NULL )
    : NCursesMenuItem (p_name, p_descript),
      p_fct (fct) {
  }

  NCursesMenuCallbackItem& operator=(const NCursesMenuCallbackItem& rhs)
  {
    if (this != &rhs) {
      *this = rhs;
    }
    return *this;
  }

  NCursesMenuCallbackItem(const NCursesMenuCallbackItem& rhs)
    : NCursesMenuItem(rhs),
      p_fct(0)
  {
  }

  virtual ~NCursesMenuCallbackItem() THROWS(NCursesException);

  bool action() NCURSES_OVERRIDE;
};

  // This are the built-in hook functions in this C++ binding. In C++ we use
  // virtual member functions (see below On_..._Init and On_..._Termination)
  // to provide this functionality in an object oriented manner.
extern "C" {
  void _nc_xx_mnu_init(MENU *);
  void _nc_xx_mnu_term(MENU *);
  void _nc_xx_itm_init(MENU *);
  void _nc_xx_itm_term(MENU *);
}

//
// -------------------------------------------------------------------------
// This wraps the MENU type of <ncursesw/menu.h>
// -------------------------------------------------------------------------
//
class NCURSES_CXX_IMPEXP NCursesMenu : public NCursesPanel
{
protected:
  MENU *menu;

private:
  NCursesWindow* sub;   // the subwindow object
  bool b_sub_owner;     // is this our own subwindow?
  bool b_framed;        // has the menu a border?
  bool b_autoDelete;    // Delete items when deleting menu?

  NCursesMenuItem** my_items; // The array of items for this menu

  // This structure is used for the menu's user data field to link the
  // MENU* to the C++ object and to provide extra space for a user pointer.
  typedef struct {
    void*              m_user;      // the pointer for the user's data
    const NCursesMenu* m_back;      // backward pointer to C++ object
    const MENU*        m_owner;
  } UserHook;

  // Get the backward pointer to the C++ object from a MENU
  static inline NCursesMenu* getHook(const MENU *m) {
    UserHook* hook = STATIC_CAST(UserHook*)(::menu_userptr(m));
    assert(hook != 0 && hook->m_owner==m);
    return const_cast<NCursesMenu*>(hook->m_back);
  }

  friend void _nc_xx_mnu_init(MENU *);
  friend void _nc_xx_mnu_term(MENU *);
  friend void _nc_xx_itm_init(MENU *);
  friend void _nc_xx_itm_term(MENU *);

  // Calculate ITEM* array for the menu
  ITEM** mapItems(NCursesMenuItem* nitems[]);

protected:
  // internal routines
  inline void set_user(void *user) {
    UserHook* uptr = STATIC_CAST(UserHook*)(::menu_userptr (menu));
    assert (uptr != 0 && uptr->m_back==this && uptr->m_owner==menu);
    uptr->m_user = user;
  }

  inline void *get_user() {
    UserHook* uptr = STATIC_CAST(UserHook*)(::menu_userptr (menu));
    assert (uptr != 0 && uptr->m_back==this && uptr->m_owner==menu);
    return uptr->m_user;
  }

  void InitMenu (NCursesMenuItem* menu[],
		 bool with_frame,
		 bool autoDeleteItems);

  inline void OnError (int err) const THROW2(NCursesException const, NCursesMenuException) {
    if (err != E_OK)
      THROW(new NCursesMenuException (this, err));
  }

  // this wraps the menu_driver call.
  virtual int driver (int c) ;

  // 'Internal' constructor to create a menu without association to
  // an array of items.
  NCursesMenu( int  nlines,
	       int  ncols,
	       int  begin_y = 0,
	       int  begin_x = 0)
    : NCursesPanel(nlines,ncols,begin_y,begin_x),
      menu (STATIC_CAST(MENU*)(0)),
      sub(0),
      b_sub_owner(0),
      b_framed(0),
      b_autoDelete(0),
      my_items(0)
  {
  }

public:
  // Make a full window size menu
  NCursesMenu (NCursesMenuItem* Items[],
	       bool with_frame=FALSE,        // Reserve space for a frame?
	       bool autoDelete_Items=FALSE)  // Autocleanup of Items?
    : NCursesPanel(),
      menu(0),
      sub(0),
      b_sub_owner(0),
      b_framed(0),
      b_autoDelete(0),
      my_items(0)
  {
      InitMenu(Items, with_frame, autoDelete_Items);
  }

  // Make a menu with a window of this size.
  NCursesMenu (NCursesMenuItem* Items[],
	       int  nlines,
	       int  ncols,
	       int  begin_y = 0,
	       int  begin_x = 0,
	       bool with_frame=FALSE,        // Reserve space for a frame?
	       bool autoDelete_Items=FALSE)  // Autocleanup of Items?
    : NCursesPanel(nlines, ncols, begin_y, begin_x),
      menu(0),
      sub(0),
      b_sub_owner(0),
      b_framed(0),
      b_autoDelete(0),
      my_items(0)
  {
      InitMenu(Items, with_frame, autoDelete_Items);
  }

  NCursesMenu& operator=(const NCursesMenu& rhs)
  {
    if (this != &rhs) {
      *this = rhs;
      NCursesPanel::operator=(rhs);
    }
    return *this;
  }

  NCursesMenu(const NCursesMenu& rhs)
    : NCursesPanel(rhs),
      menu(rhs.menu),
      sub(rhs.sub),
      b_sub_owner(rhs.b_sub_owner),
      b_framed(rhs.b_framed),
      b_autoDelete(rhs.b_autoDelete),
      my_items(rhs.my_items)
  {
  }

  virtual ~NCursesMenu () THROWS(NCursesException);

  // Retrieve the menus subwindow
  inline NCursesWindow& subWindow() const {
    assert(sub!=NULL);
    return *sub;
  }

  // Set the menus subwindow
  void setSubWindow(NCursesWindow& sub);

  // Set these items for the menu
  inline void setItems(NCursesMenuItem* Items[]) {
    OnError(::set_menu_items(menu,mapItems(Items)));
  }

  // Remove the menu from the screen
  inline void unpost (void) {
    OnError (::unpost_menu (menu));
  }

  // Post the menu to the screen if flag is true, unpost it otherwise
  inline void post(bool flag = TRUE) {
    flag ? OnError (::post_menu(menu)) : OnError (::unpost_menu (menu));
  }

  // Get the number of rows and columns for this menu
  inline void scale (int& mrows, int& mcols) const  {
    OnError (::scale_menu (menu, &mrows, &mcols));
  }

  // Set the format of this menu
  inline void set_format(int mrows, int mcols) {
    OnError (::set_menu_format(menu, mrows, mcols));
  }

  // Get the format of this menu
  inline void menu_format(int& rows,int& ncols) {
    ::menu_format(menu,&rows,&ncols);
  }

  // Items of the menu
  inline NCursesMenuItem* items() const {
    return *my_items;
  }

  // Get the number of items in this menu
  inline int count() const {
    return ::item_count(menu);
  }

  // Get the current item (i.e. the one the cursor is located)
  inline NCursesMenuItem* current_item() const {
    return my_items[::item_index(::current_item(menu))];
  }

  // Get the marker string
  inline const char* mark() const {
    return ::menu_mark(menu);
  }

  // Set the marker string
  inline void set_mark(const char *marker) {
    OnError (::set_menu_mark (menu, marker));
  }

  // Get the name of the request code c
  inline static const char* request_name(int c) {
    return ::menu_request_name(c);
  }

  // Get the current pattern
  inline char* pattern() const {
    return ::menu_pattern(menu);
  }

  // true if there is a pattern match, false otherwise.
  bool set_pattern (const char *pat);

  // set the default attributes for the menu
  // i.e. set fore, back and grey attribute
  virtual void setDefaultAttributes();

  // Get the menus background attributes
  inline chtype back() const {
    return ::menu_back(menu);
  }

  // Get the menus foreground attributes
  inline chtype fore() const {
    return ::menu_fore(menu);
  }

  // Get the menus grey attributes (used for unselectable items)
  inline chtype grey() const {
    return ::menu_grey(menu);
  }

  // Set the menus background attributes
  inline chtype set_background(chtype a) {
    return ::set_menu_back(menu,a);
  }

  // Set the menus foreground attributes
  inline chtype set_foreground(chtype a) {
    return ::set_menu_fore(menu,a);
  }

  // Set the menus grey attributes (used for unselectable items)
  inline chtype set_grey(chtype a) {
    return ::set_menu_grey(menu,a);
  }

  inline void options_on (Menu_Options opts) {
    OnError (::menu_opts_on (menu,opts));
  }

  inline void options_off(Menu_Options opts) {
    OnError (::menu_opts_off(menu,opts));
  }

  inline Menu_Options options() const {
    return ::menu_opts(menu);
  }

  inline void set_options (Menu_Options opts) {
    OnError (::set_menu_opts (menu,opts));
  }

  inline int pad() const {
    return ::menu_pad(menu);
  }

  inline void set_pad (int padch) {
    OnError (::set_menu_pad (menu, padch));
  }

  // Position the cursor to the current item
  inline void position_cursor () const {
    OnError (::pos_menu_cursor (menu));
  }

  // Set the current item
  inline void set_current(NCursesMenuItem& I) {
    OnError (::set_current_item(menu, I.item));
  }

  // Get the current top row of the menu
  inline int top_row (void) const {
    return ::top_row (menu);
  }

  // Set the current top row of the menu
  inline void set_top_row (int row) {
    OnError (::set_top_row (menu, row));
  }

  // spacing control
  // Set the spacing for the menu
  inline void setSpacing(int spc_description,
			 int spc_rows,
			 int spc_columns) {
    OnError(::set_menu_spacing(menu,
			       spc_description,
			       spc_rows,
			       spc_columns));
  }

  // Get the spacing info for the menu
  inline void Spacing(int& spc_description,
		      int& spc_rows,
		      int& spc_columns) const {
    OnError(::menu_spacing(menu,
			   &spc_description,
			   &spc_rows,
			   &spc_columns));
  }

  // Decorations
  inline void frame(const char *title=NULL, const char* btitle=NULL) NCURSES_OVERRIDE {
    if (b_framed)
      NCursesPanel::frame(title,btitle);
    else
      OnError(E_SYSTEM_ERROR);
  }

  inline void boldframe(const char *title=NULL, const char* btitle=NULL) NCURSES_OVERRIDE {
    if (b_framed)
      NCursesPanel::boldframe(title,btitle);
    else
      OnError(E_SYSTEM_ERROR);
  }

  inline void label(const char *topLabel, const char *bottomLabel) NCURSES_OVERRIDE {
    if (b_framed)
      NCursesPanel::label(topLabel,bottomLabel);
    else
      OnError(E_SYSTEM_ERROR);
  }

  // -----
  // Hooks
  // -----

  // Called after the menu gets repositioned in its window.
  // This is especially true if the menu is posted.
  virtual void On_Menu_Init();

  // Called before the menu gets repositioned in its window.
  // This is especially true if the menu is unposted.
  virtual void On_Menu_Termination();

  // Called after the item became the current item
  virtual void On_Item_Init(NCursesMenuItem& item);

  // Called before this item is left as current item.
  virtual void On_Item_Termination(NCursesMenuItem& item);

  // Provide a default key virtualization. Translate the keyboard
  // code c into a menu request code.
  // The default implementation provides a hopefully straightforward
  // mapping for the most common keystrokes and menu requests.
  virtual int virtualize(int c);


  // Operators
  inline NCursesMenuItem* operator[](int i) const {
    if ( (i < 0) || (i >= ::item_count (menu)) )
      OnError (E_BAD_ARGUMENT);
    return (my_items[i]);
  }

  // Perform the menu's operation
  // Return the item where you left the selection mark for a single
  // selection menu, or NULL for a multivalued menu.
  virtual NCursesMenuItem* operator()(void);

  // --------------------
  // Exception handlers
  // Called by operator()
  // --------------------

  // Called if the request is denied
  virtual void On_Request_Denied(int c) const;

  // Called if the item is not selectable
  virtual void On_Not_Selectable(int c) const;

  // Called if pattern doesn't match
  virtual void On_No_Match(int c) const;

  // Called if the command is unknown
  virtual void On_Unknown_Command(int c) const;

};
//
// -------------------------------------------------------------------------
// This is the typical C++ typesafe way to allow to attach
// user data to an item of a menu. Its assumed that the user
// data belongs to some class T. Use T as template argument
// to create a UserItem.
// -------------------------------------------------------------------------
//
template<class T> class NCURSES_CXX_IMPEXP NCursesUserItem : public NCursesMenuItem
{
public:
  NCursesUserItem (const char* p_name,
		   const char* p_descript = NULL,
		   const T* p_UserData    = STATIC_CAST(T*)(0))
    : NCursesMenuItem (p_name, p_descript) {
      if (item)
	OnError (::set_item_userptr (item, const_cast<void *>(reinterpret_cast<const void*>(p_UserData))));
  }

  virtual ~NCursesUserItem() THROWS(NCursesException) {}

  inline const T* UserData (void) const {
    return reinterpret_cast<const T*>(::item_userptr (item));
  };

  inline virtual void setUserData(const T* p_UserData) {
    if (item)
      OnError (::set_item_userptr (item, const_cast<void *>(reinterpret_cast<const void *>(p_UserData))));
  }
};
//
// -------------------------------------------------------------------------
// The same mechanism is used to attach user data to a menu
// -------------------------------------------------------------------------
//
template<class T> class NCURSES_CXX_IMPEXP NCursesUserMenu : public NCursesMenu
{
protected:
  NCursesUserMenu( int  nlines,
		   int  ncols,
		   int  begin_y = 0,
		   int  begin_x = 0,
		   const T* p_UserData = STATIC_CAST(T*)(0))
    : NCursesMenu(nlines,ncols,begin_y,begin_x) {
      if (menu)
	set_user (const_cast<void *>(reinterpret_cast<const void*>(p_UserData)));
  }

public:
  NCursesUserMenu (NCursesMenuItem* Items[],
		   const T* p_UserData = STATIC_CAST(T*)(0),
		   bool with_frame=FALSE,
		   bool autoDelete_Items=FALSE)
    : NCursesMenu (&Items, with_frame, autoDelete_Items) {
      if (menu)
	set_user (const_cast<void *>(reinterpret_cast<const void*>(p_UserData)));
  };

  NCursesUserMenu (NCursesMenuItem* Items[],
		   int nlines,
		   int ncols,
		   int begin_y = 0,
		   int begin_x = 0,
		   const T* p_UserData = STATIC_CAST(T*)(0),
		   bool with_frame=FALSE)
    : NCursesMenu (&Items, nlines, ncols, begin_y, begin_x, with_frame) {
      if (menu)
	set_user (const_cast<void *>(reinterpret_cast<const void*>(p_UserData)));
  };

  virtual ~NCursesUserMenu() THROWS(NCursesException) {
  };

  inline T* UserData (void) {
    return reinterpret_cast<T*>(get_user ());
  };

  inline virtual void setUserData (const T* p_UserData) {
    if (menu)
      set_user (const_cast<void *>(reinterpret_cast<const void*>(p_UserData)));
  }
};

#endif /* NCURSES_CURSESM_H_incl */
