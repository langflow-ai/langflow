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

// $Id: cursesf.h,v 1.39 2022/08/20 20:52:15 tom Exp $

#ifndef NCURSES_CURSESF_H_incl
#define NCURSES_CURSESF_H_incl 1

#include <ncursesw/cursesp.h>

#ifndef __EXT_QNX
#include <string.h>
#endif

extern "C" {
#  include <ncursesw/form.h>
}
//
// -------------------------------------------------------------------------
// The abstract base class for builtin and user defined Fieldtypes.
// -------------------------------------------------------------------------
//
class NCURSES_CXX_IMPEXP NCursesFormField; // forward declaration

// Class to represent builtin field types as well as C++ written new
// fieldtypes (see classes UserDefineFieldType...
class NCURSES_CXX_IMPEXP NCursesFieldType
{
  friend class NCursesFormField;

protected:
  FIELDTYPE* fieldtype;

  inline void OnError(int err) const THROW2(NCursesException const, NCursesFormException) {
    if (err!=E_OK)
      THROW(new NCursesFormException (err));
  }

  NCursesFieldType(FIELDTYPE *f) : fieldtype(f) {
  }

  virtual ~NCursesFieldType() {}

  // Set the fields f fieldtype to this one.
  virtual void set(NCursesFormField& f) = 0;

public:
  NCursesFieldType()
    : fieldtype(STATIC_CAST(FIELDTYPE*)(0))
  {
  }

  NCursesFieldType& operator=(const NCursesFieldType& rhs)
  {
    if (this != &rhs) {
      *this = rhs;
    }
    return *this;
  }

  NCursesFieldType(const NCursesFieldType& rhs)
    : fieldtype(rhs.fieldtype)
  {
  }

};

//
// -------------------------------------------------------------------------
// The class representing a forms field, wrapping the lowlevel FIELD struct
// -------------------------------------------------------------------------
//
class NCURSES_CXX_IMPEXP NCursesFormField
{
  friend class NCursesForm;

protected:
  FIELD *field;		     // lowlevel structure
  NCursesFieldType* ftype;   // Associated field type

  // Error handler
  inline void OnError (int err) const THROW2(NCursesException const, NCursesFormException) {
    if (err != E_OK)
      THROW(new NCursesFormException (err));
  }

public:
  // Create a 'Null' field. Can be used to delimit a field list
  NCursesFormField()
    : field(STATIC_CAST(FIELD*)(0)),
      ftype(STATIC_CAST(NCursesFieldType*)(0))
  {
  }

  // Create a new field
  NCursesFormField (int rows,
		    int ncols,
		    int first_row = 0,
		    int first_col = 0,
		    int offscreen_rows = 0,
		    int additional_buffers = 0)
    : field(0),
      ftype(STATIC_CAST(NCursesFieldType*)(0))
  {
      field = ::new_field(rows, ncols, first_row, first_col,
			  offscreen_rows, additional_buffers);
      if (!field)
	OnError(errno);
  }

  NCursesFormField& operator=(const NCursesFormField& rhs)
  {
    if (this != &rhs) {
      *this = rhs;
    }
    return *this;
  }

  NCursesFormField(const NCursesFormField& rhs)
    : field(rhs.field), ftype(rhs.ftype)
  {
  }

  virtual ~NCursesFormField () THROWS(NCursesException);

  // Duplicate the field at a new position
  inline NCursesFormField* dup(int first_row, int first_col)
  {
    NCursesFormField* f = new NCursesFormField();
    if (!f)
      OnError(E_SYSTEM_ERROR);
    else {
      f->ftype = ftype;
      f->field = ::dup_field(field,first_row,first_col);
      if (!f->field)
	OnError(errno);
    }
    return f;
  }

  // Link the field to a new location
  inline NCursesFormField* link(int first_row, int first_col) {
    NCursesFormField* f = new NCursesFormField();
    if (!f)
      OnError(E_SYSTEM_ERROR);
    else {
      f->ftype = ftype;
      f->field = ::link_field(field,first_row,first_col);
      if (!f->field)
	OnError(errno);
    }
    return f;
  }

  // Get the lowlevel field representation
  inline FIELD* get_field() const {
    return field;
  }

  // Retrieve info about the field
  inline void info(int& rows, int& ncols,
		   int& first_row, int& first_col,
		   int& offscreen_rows, int& additional_buffers) const {
    OnError(::field_info(field, &rows, &ncols,
			 &first_row, &first_col,
			 &offscreen_rows, &additional_buffers));
  }

  // Retrieve info about the fields dynamic properties.
  inline void dynamic_info(int& dynamic_rows, int& dynamic_cols,
			   int& max_growth) const {
    OnError(::dynamic_field_info(field, &dynamic_rows, &dynamic_cols,
				 &max_growth));
  }

  // For a dynamic field you may set the maximum growth limit.
  // A zero means unlimited growth.
  inline void set_maximum_growth(int growth = 0) {
    OnError(::set_max_field(field,growth));
  }

  // Move the field to a new position
  inline void move(int row, int col) {
    OnError(::move_field(field,row,col));
  }

  // Mark the field to start a new page
  inline void new_page(bool pageFlag = FALSE) {
    OnError(::set_new_page(field,pageFlag));
  }

  // Retrieve whether or not the field starts a new page.
  inline bool is_new_page() const {
    return ::new_page(field);
  }

  // Set the justification for the field
  inline void set_justification(int just) {
    OnError(::set_field_just(field,just));
  }

  // Retrieve the fields justification
  inline int justification() const {
    return ::field_just(field);
  }
  // Set the foreground attribute for the field
  inline void set_foreground(chtype foreground) {
    OnError(::set_field_fore(field,foreground));
  }

  // Retrieve the fields foreground attribute
  inline chtype fore() const {
    return ::field_fore(field);
  }

  // Set the background attribute for the field
  inline void set_background(chtype background) {
    OnError(::set_field_back(field,background));
  }

  // Retrieve the fields background attribute
  inline chtype back() const {
    return ::field_back(field);
  }

  // Set the padding character for the field
  inline void set_pad_character(int padding) {
    OnError(::set_field_pad(field, padding));
  }

  // Retrieve the fields padding character
  inline int pad() const {
    return ::field_pad(field);
  }

  // Switch on the fields options
  inline void options_on (Field_Options opts) {
    OnError (::field_opts_on (field, opts));
  }

  // Switch off the fields options
  inline void options_off (Field_Options opts) {
    OnError (::field_opts_off (field, opts));
  }

  // Retrieve the fields options
  inline Field_Options options () const {
    return ::field_opts (field);
  }

  // Set the fields options
  inline void set_options (Field_Options opts) {
    OnError (::set_field_opts (field, opts));
  }

  // Mark the field as changed
  inline void set_changed(bool changeFlag = TRUE) {
    OnError(::set_field_status(field,changeFlag));
  }

  // Test whether or not the field is marked as changed
  inline bool changed() const {
    return ::field_status(field);
  }

  // Return the index of the field in the field array of a form
  // or -1 if the field is not associated to a form
  inline int (index)() const {
    return ::field_index(field);
  }

  // Store a value in a fields buffer. The default buffer is nr. 0
  inline void set_value(const char *val, int buffer = 0) {
    OnError(::set_field_buffer(field,buffer,val));
  }

  // Retrieve the value of a fields buffer. The default buffer is nr. 0
  inline char* value(int buffer = 0) const {
    return ::field_buffer(field,buffer);
  }

  // Set the validation type of the field.
  inline void set_fieldtype(NCursesFieldType& f) {
    ftype = &f;
    f.set(*this); // A good friend may do that...
  }

  // Retrieve the validation type of the field.
  inline NCursesFieldType* fieldtype() const {
    return ftype;
  }

};

  // This are the built-in hook functions in this C++ binding. In C++ we use
  // virtual member functions (see below On_..._Init and On_..._Termination)
  // to provide this functionality in an object oriented manner.
extern "C" {
  void _nc_xx_frm_init(FORM *);
  void _nc_xx_frm_term(FORM *);
  void _nc_xx_fld_init(FORM *);
  void _nc_xx_fld_term(FORM *);
}

//
// -------------------------------------------------------------------------
// The class representing a form, wrapping the lowlevel FORM struct
// -------------------------------------------------------------------------
//
class NCURSES_CXX_IMPEXP NCursesForm : public NCursesPanel
{
protected:
  FORM* form;  // the lowlevel structure

private:
  NCursesWindow* sub;   // the subwindow object
  bool b_sub_owner;     // is this our own subwindow?
  bool b_framed;	// has the form a border?
  bool b_autoDelete;    // Delete fields when deleting form?

  NCursesFormField** my_fields; // The array of fields for this form

  // This structure is used for the form's user data field to link the
  // FORM* to the C++ object and to provide extra space for a user pointer.
  typedef struct {
    void*	       m_user;	    // the pointer for the user's data
    const NCursesForm* m_back;      // backward pointer to C++ object
    const FORM*	       m_owner;
  } UserHook;

  // Get the backward pointer to the C++ object from a FORM
  static inline NCursesForm* getHook(const FORM *f) {
    UserHook* hook = reinterpret_cast<UserHook*>(::form_userptr(f));
    assert(hook != 0 && hook->m_owner==f);
    return const_cast<NCursesForm*>(hook->m_back);
  }

  friend void _nc_xx_frm_init(FORM *);
  friend void _nc_xx_frm_term(FORM *);
  friend void _nc_xx_fld_init(FORM *);
  friend void _nc_xx_fld_term(FORM *);

  // Calculate FIELD* array for the menu
  FIELD** mapFields(NCursesFormField* nfields[]);

protected:
  // internal routines
  inline void set_user(void *user) {
    UserHook* uptr = reinterpret_cast<UserHook*>(::form_userptr (form));
    assert (uptr != 0 && uptr->m_back==this && uptr->m_owner==form);
    uptr->m_user = user;
  }

  inline void *get_user() {
    UserHook* uptr = reinterpret_cast<UserHook*>(::form_userptr (form));
    assert (uptr != 0 && uptr->m_back==this && uptr->m_owner==form);
    return uptr->m_user;
  }

  void InitForm (NCursesFormField* Fields[],
		 bool with_frame,
		 bool autoDeleteFields);

  inline void OnError (int err) const THROW2(NCursesException const, NCursesFormException) {
    if (err != E_OK)
      THROW(new NCursesFormException (err));
  }

  // this wraps the form_driver call.
  virtual int driver (int c) ;

  // 'Internal' constructor, builds an object without association to a
  // field array.
  NCursesForm( int  nlines,
	       int  ncols,
	       int  begin_y = 0,
	       int  begin_x = 0)
    : NCursesPanel(nlines, ncols, begin_y, begin_x),
      form (STATIC_CAST(FORM*)(0)),
      sub(0),
      b_sub_owner(0),
      b_framed(0),
      b_autoDelete(0),
      my_fields(0)
  {
  }

public:
  // Create form for the default panel.
  NCursesForm (NCursesFormField* Fields[],
	       bool with_frame=FALSE,	      // reserve space for a frame?
	       bool autoDelete_Fields=FALSE)  // do automatic cleanup?
    : NCursesPanel(),
      form(0),
      sub(0),
      b_sub_owner(0),
      b_framed(0),
      b_autoDelete(0),
      my_fields(0)
  {
    InitForm(Fields, with_frame, autoDelete_Fields);
  }

  // Create a form in a panel with the given position and size.
  NCursesForm (NCursesFormField* Fields[],
	       int  nlines,
	       int  ncols,
	       int  begin_y,
	       int  begin_x,
	       bool with_frame=FALSE,	     // reserve space for a frame?
	       bool autoDelete_Fields=FALSE) // do automatic cleanup?
    : NCursesPanel(nlines, ncols, begin_y, begin_x),
      form(0),
      sub(0),
      b_sub_owner(0),
      b_framed(0),
      b_autoDelete(0),
      my_fields(0)
  {
      InitForm(Fields, with_frame, autoDelete_Fields);
  }

  NCursesForm& operator=(const NCursesForm& rhs)
  {
    if (this != &rhs) {
      *this = rhs;
      NCursesPanel::operator=(rhs);
    }
    return *this;
  }

  NCursesForm(const NCursesForm& rhs)
    : NCursesPanel(rhs),
      form(rhs.form),
      sub(rhs.sub),
      b_sub_owner(rhs.b_sub_owner),
      b_framed(rhs.b_framed),
      b_autoDelete(rhs.b_autoDelete),
      my_fields(rhs.my_fields)
  {
  }

  virtual ~NCursesForm() THROWS(NCursesException);

  // Set the default attributes for the form
  virtual void setDefaultAttributes();

  // Retrieve current field of the form.
  inline NCursesFormField* current_field() const {
    return my_fields[::field_index(::current_field(form))];
  }

  // Set the forms subwindow
  void setSubWindow(NCursesWindow& sub);

  // Set these fields for the form
  inline void setFields(NCursesFormField* Fields[]) {
    OnError(::set_form_fields(form,mapFields(Fields)));
  }

  // Remove the form from the screen
  inline void unpost (void) {
    OnError (::unpost_form (form));
  }

  // Post the form to the screen if flag is true, unpost it otherwise
  inline void post(bool flag = TRUE) {
    OnError (flag ? ::post_form(form) : ::unpost_form (form));
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

  // Called after the form gets repositioned in its window.
  // This is especially true if the form is posted.
  virtual void On_Form_Init();

  // Called before the form gets repositioned in its window.
  // This is especially true if the form is unposted.
  virtual void On_Form_Termination();

  // Called after the field became the current field
  virtual void On_Field_Init(NCursesFormField& field);

  // Called before this field is left as current field.
  virtual void On_Field_Termination(NCursesFormField& field);

  // Calculate required window size for the form.
  void scale(int& rows, int& ncols) const {
    OnError(::scale_form(form,&rows,&ncols));
  }

  // Retrieve number of fields in the form.
  int count() const {
    return ::field_count(form);
  }

  // Make the page the current page of the form.
  void set_page(int pageNum) {
    OnError(::set_form_page(form, pageNum));
  }

  // Retrieve current page number
  int page() const {
    return ::form_page(form);
  }

  // Switch on the forms options
  inline void options_on (Form_Options opts) {
    OnError (::form_opts_on (form, opts));
  }

  // Switch off the forms options
  inline void options_off (Form_Options opts) {
    OnError (::form_opts_off (form, opts));
  }

  // Retrieve the forms options
  inline Form_Options options () const {
    return ::form_opts (form);
  }

  // Set the forms options
  inline void set_options (Form_Options opts) {
    OnError (::set_form_opts (form, opts));
  }

  // Are there more data in the current field after the data shown
  inline bool data_ahead() const {
    return ::data_ahead(form);
  }

  // Are there more data in the current field before the data shown
  inline bool data_behind() const {
    return ::data_behind(form);
  }

  // Position the cursor to the current field
  inline void position_cursor () {
    OnError (::pos_form_cursor (form));
  }
  // Set the current field
  inline void set_current(NCursesFormField& F) {
    OnError (::set_current_field(form, F.field));
  }

  // Provide a default key virtualization. Translate the keyboard
  // code c into a form request code.
  // The default implementation provides a hopefully straightforward
  // mapping for the most common keystrokes and form requests.
  virtual int virtualize(int c);

  // Operators
  inline NCursesFormField* operator[](int i) const {
    if ( (i < 0) || (i >= ::field_count (form)) )
      OnError (E_BAD_ARGUMENT);
    return my_fields[i];
  }

  // Perform the menu's operation
  // Return the field where you left the form.
  virtual NCursesFormField* operator()(void);

  // Exception handlers. The default is a Beep.
  virtual void On_Request_Denied(int c) const;
  virtual void On_Invalid_Field(int c) const;
  virtual void On_Unknown_Command(int c) const;

};

//
// -------------------------------------------------------------------------
// This is the typical C++ typesafe way to allow to attach
// user data to a field of a form. Its assumed that the user
// data belongs to some class T. Use T as template argument
// to create a UserField.
// -------------------------------------------------------------------------
template<class T> class NCURSES_CXX_IMPEXP NCursesUserField : public NCursesFormField
{
public:
  NCursesUserField (int rows,
		    int ncols,
		    int first_row = 0,
		    int first_col = 0,
		    const T* p_UserData = STATIC_CAST(T*)(0),
		    int offscreen_rows = 0,
		    int additional_buffers = 0)
    : NCursesFormField (rows, ncols,
			first_row, first_col,
			offscreen_rows, additional_buffers) {
      if (field)
	OnError(::set_field_userptr(field, STATIC_CAST(void *)(p_UserData)));
  }

  virtual ~NCursesUserField() THROWS(NCursesException) {};

  inline const T* UserData (void) const {
    return reinterpret_cast<const T*>(::field_userptr (field));
  }

  inline virtual void setUserData(const T* p_UserData) {
    if (field)
      OnError (::set_field_userptr (field, STATIC_CAST(void *)(p_UserData)));
  }
};
//
// -------------------------------------------------------------------------
// The same mechanism is used to attach user data to a form
// -------------------------------------------------------------------------
//
template<class T> class NCURSES_CXX_IMPEXP NCursesUserForm : public NCursesForm
{
protected:
  // 'Internal' constructor, builds an object without association to a
  // field array.
  NCursesUserForm( int  nlines,
		   int  ncols,
		   int  begin_y = 0,
		   int  begin_x = 0,
		   const T* p_UserData = STATIC_CAST(T*)(0))
    : NCursesForm(nlines,ncols,begin_y,begin_x) {
      if (form)
	set_user (const_cast<void *>(reinterpret_cast<const void*>
				     (p_UserData)));
  }

public:
  NCursesUserForm (NCursesFormField* Fields[],
		   const T* p_UserData = STATIC_CAST(T*)(0),
		   bool with_frame=FALSE,
		   bool autoDelete_Fields=FALSE)
    : NCursesForm (&Fields, with_frame, autoDelete_Fields) {
      if (form)
	set_user (const_cast<void *>(reinterpret_cast<const void*>(p_UserData)));
  };

  NCursesUserForm (NCursesFormField* Fields[],
		   int nlines,
		   int ncols,
		   int begin_y = 0,
		   int begin_x = 0,
		   const T* p_UserData = STATIC_CAST(T*)(0),
		   bool with_frame=FALSE,
		   bool autoDelete_Fields=FALSE)
    : NCursesForm (&Fields, nlines, ncols, begin_y, begin_x,
		   with_frame, autoDelete_Fields) {
      if (form)
	set_user (const_cast<void *>(reinterpret_cast<const void*>
				     (p_UserData)));
  };

  virtual ~NCursesUserForm() THROWS(NCursesException) {
  };

  inline T* UserData (void) {
    return reinterpret_cast<T*>(get_user ());
  };

  inline virtual void setUserData (const T* p_UserData) {
    if (form)
      set_user (const_cast<void *>(reinterpret_cast<const void*>(p_UserData)));
  }

};
//
// -------------------------------------------------------------------------
// Builtin Fieldtypes
// -------------------------------------------------------------------------
//
class NCURSES_CXX_IMPEXP Alpha_Field : public NCursesFieldType
{
private:
  int min_field_width;

  void set(NCursesFormField& f) NCURSES_OVERRIDE {
    OnError(::set_field_type(f.get_field(),fieldtype,min_field_width));
  }

public:
  explicit Alpha_Field(int width)
    : NCursesFieldType(TYPE_ALPHA),
      min_field_width(width) {
  }
};

class NCURSES_CXX_IMPEXP Alphanumeric_Field : public NCursesFieldType
{
private:
  int min_field_width;

  void set(NCursesFormField& f) NCURSES_OVERRIDE {
    OnError(::set_field_type(f.get_field(),fieldtype,min_field_width));
  }

public:
  explicit Alphanumeric_Field(int width)
    : NCursesFieldType(TYPE_ALNUM),
      min_field_width(width) {
  }
};

class NCURSES_CXX_IMPEXP Integer_Field : public NCursesFieldType
{
private:
  int precision;
  long lower_limit, upper_limit;

  void set(NCursesFormField& f) NCURSES_OVERRIDE {
    OnError(::set_field_type(f.get_field(),fieldtype,
			     precision,lower_limit,upper_limit));
  }

public:
  Integer_Field(int prec, long low=0L, long high=0L)
    : NCursesFieldType(TYPE_INTEGER),
      precision(prec), lower_limit(low), upper_limit(high) {
  }
};

class NCURSES_CXX_IMPEXP Numeric_Field : public NCursesFieldType
{
private:
  int precision;
  double lower_limit, upper_limit;

  void set(NCursesFormField& f) NCURSES_OVERRIDE {
    OnError(::set_field_type(f.get_field(),fieldtype,
			     precision,lower_limit,upper_limit));
  }

public:
  Numeric_Field(int prec, double low=0.0, double high=0.0)
    : NCursesFieldType(TYPE_NUMERIC),
      precision(prec), lower_limit(low), upper_limit(high) {
  }
};

class NCURSES_CXX_IMPEXP Regular_Expression_Field : public NCursesFieldType
{
private:
  char* regex;

  void set(NCursesFormField& f) NCURSES_OVERRIDE {
    OnError(::set_field_type(f.get_field(),fieldtype,regex));
  }

  void copy_regex(const char *source)
  {
    regex = new char[1 + ::strlen(source)];
    (::strcpy)(regex, source);
  }

public:
  explicit Regular_Expression_Field(const char *expr)
    : NCursesFieldType(TYPE_REGEXP),
      regex(NULL)
  {
    copy_regex(expr);
  }

  Regular_Expression_Field& operator=(const Regular_Expression_Field& rhs)
  {
    if (this != &rhs) {
      *this = rhs;
      copy_regex(rhs.regex);
      NCursesFieldType::operator=(rhs);
    }
    return *this;
  }

  Regular_Expression_Field(const Regular_Expression_Field& rhs)
    : NCursesFieldType(rhs),
      regex(NULL)
  {
    copy_regex(rhs.regex);
  }

  ~Regular_Expression_Field() {
    delete[] regex;
  }
};

class NCURSES_CXX_IMPEXP Enumeration_Field : public NCursesFieldType
{
private:
  const char** list;
  int case_sensitive;
  int non_unique_matches;

  void set(NCursesFormField& f) NCURSES_OVERRIDE {
    OnError(::set_field_type(f.get_field(),fieldtype,
			     list,case_sensitive,non_unique_matches));
  }
public:
  Enumeration_Field(const char* enums[],
		    bool case_sens=FALSE,
		    bool non_unique=FALSE)
    : NCursesFieldType(TYPE_ENUM),
      list(enums),
      case_sensitive(case_sens ? -1 : 0),
      non_unique_matches(non_unique ? -1 : 0) {
  }

  Enumeration_Field& operator=(const Enumeration_Field& rhs)
  {
    if (this != &rhs) {
      *this = rhs;
      NCursesFieldType::operator=(rhs);
    }
    return *this;
  }

  Enumeration_Field(const Enumeration_Field& rhs)
    : NCursesFieldType(rhs),
      list(rhs.list),
      case_sensitive(rhs.case_sensitive),
      non_unique_matches(rhs.non_unique_matches)
  {
  }
};

class NCURSES_CXX_IMPEXP IPV4_Address_Field : public NCursesFieldType
{
private:
  void set(NCursesFormField& f) NCURSES_OVERRIDE {
    OnError(::set_field_type(f.get_field(),fieldtype));
  }

public:
  IPV4_Address_Field() : NCursesFieldType(TYPE_IPV4) {
  }
};

extern "C" {
  bool _nc_xx_fld_fcheck(FIELD *, const void*);
  bool _nc_xx_fld_ccheck(int c, const void *);
  void* _nc_xx_fld_makearg(va_list*);
}

//
// -------------------------------------------------------------------------
// Abstract base class for User-Defined Fieldtypes
// -------------------------------------------------------------------------
//
class NCURSES_CXX_IMPEXP UserDefinedFieldType : public NCursesFieldType
{
  friend class UDF_Init; // Internal helper to set up statics
private:
  // For all C++ defined fieldtypes we need only one generic lowlevel
  // FIELDTYPE* element.
  static FIELDTYPE* generic_fieldtype;

protected:
  // This are the functions required by the low level libforms functions
  // to construct a fieldtype.
  friend bool _nc_xx_fld_fcheck(FIELD *, const void*);
  friend bool _nc_xx_fld_ccheck(int c, const void *);
  friend void* _nc_xx_fld_makearg(va_list*);

  void set(NCursesFormField& f) NCURSES_OVERRIDE {
    OnError(::set_field_type(f.get_field(),fieldtype,&f));
  }

protected:
  // Redefine this function to do a field validation. The argument
  // is a reference to the field you should validate.
  virtual bool field_check(NCursesFormField& f) = 0;

  // Redefine this function to do a character validation. The argument
  // is the character to be validated.
  virtual bool char_check (int c) = 0;

public:
  UserDefinedFieldType();
};

extern "C" {
  bool _nc_xx_next_choice(FIELD*, const void *);
  bool _nc_xx_prev_choice(FIELD*, const void *);
}

//
// -------------------------------------------------------------------------
// Abstract base class for User-Defined Fieldtypes with Choice functions
// -------------------------------------------------------------------------
//
class NCURSES_CXX_IMPEXP UserDefinedFieldType_With_Choice : public UserDefinedFieldType
{
  friend class UDF_Init; // Internal helper to set up statics
private:
  // For all C++ defined fieldtypes with choice functions we need only one
  // generic lowlevel FIELDTYPE* element.
  static FIELDTYPE* generic_fieldtype_with_choice;

  // This are the functions required by the low level libforms functions
  // to construct a fieldtype with choice functions.
  friend bool _nc_xx_next_choice(FIELD*, const void *);
  friend bool _nc_xx_prev_choice(FIELD*, const void *);

protected:
  // Redefine this function to do the retrieval of the next choice value.
  // The argument is a reference to the field tobe examined.
  virtual bool next    (NCursesFormField& f) = 0;

  // Redefine this function to do the retrieval of the previous choice value.
  // The argument is a reference to the field tobe examined.
  virtual bool previous(NCursesFormField& f) = 0;

public:
  UserDefinedFieldType_With_Choice();
};

#endif /* NCURSES_CURSESF_H_incl */
