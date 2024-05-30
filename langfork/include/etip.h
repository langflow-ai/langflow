// * This makes emacs happy -*-Mode: C++;-*-
/****************************************************************************
 * Copyright 2018-2021,2022 Thomas E. Dickey                                *
 * Copyright 1998-2012,2017 Free Software Foundation, Inc.                  *
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

// $Id: etip.h.in,v 1.50 2022/08/20 20:50:00 tom Exp $

#ifndef NCURSES_ETIP_H_incl
#define NCURSES_ETIP_H_incl 1

// These are substituted at configure/build time
#ifndef HAVE_BUILTIN_H
#define HAVE_BUILTIN_H 0
#endif

#ifndef HAVE_GXX_BUILTIN_H
#define HAVE_GXX_BUILTIN_H 0
#endif

#ifndef HAVE_GPP_BUILTIN_H
#define HAVE_GPP_BUILTIN_H 0
#endif

#ifndef HAVE_IOSTREAM
#define HAVE_IOSTREAM 1
#endif

#ifndef HAVE_TYPEINFO
#define HAVE_TYPEINFO 1
#endif

#ifndef HAVE_VALUES_H
#define HAVE_VALUES_H 0
#endif

#ifndef ETIP_NEEDS_MATH_H
#define ETIP_NEEDS_MATH_H 0
#endif

#ifndef ETIP_NEEDS_MATH_EXCEPTION
#define ETIP_NEEDS_MATH_EXCEPTION 0
#endif

#ifndef CPP_HAS_OVERRIDE
#define CPP_HAS_OVERRIDE 0
#endif

#ifndef CPP_HAS_PARAM_INIT
#define CPP_HAS_PARAM_INIT 0
#endif

#ifndef CPP_HAS_STATIC_CAST
#define CPP_HAS_STATIC_CAST 1
#endif

#ifndef IOSTREAM_NAMESPACE
#define IOSTREAM_NAMESPACE 1
#endif

#ifdef __GNUG__
#  if ((__GNUG__ <= 2) && (__GNUC_MINOR__ < 8))
#    if HAVE_TYPEINFO
#      include <typeinfo>
#    endif
#  endif
#endif

#if defined(__GNUG__)
#  if HAVE_BUILTIN_H || HAVE_GXX_BUILTIN_H || HAVE_GPP_BUILTIN_H
#    if ETIP_NEEDS_MATH_H
#      if ETIP_NEEDS_MATH_EXCEPTION
#        undef exception
#        define exception math_exception
#      endif
#      include <math.h>
#    endif
#    undef exception
#    define exception builtin_exception
#    if HAVE_GPP_BUILTIN_H
#     include <gpp/builtin.h>
#    elif HAVE_GXX_BUILTIN_H
#     include <g++/builtin.h>
#    else
#     include <builtin.h>
#    endif
#    undef exception
#  endif
#elif defined (__SUNPRO_CC)
#  include <generic.h>
#endif

#include <ncursesw/curses.h>

extern "C" {
#if HAVE_VALUES_H
#  include <values.h>
#endif

#include <assert.h>
#include <ncursesw/eti.h>
#include <errno.h>
}

// Language features
#if CPP_HAS_OVERRIDE
#define NCURSES_OVERRIDE override
#else
#define NCURSES_OVERRIDE /*nothing*/
#endif

#if CPP_HAS_PARAM_INIT
#define NCURSES_PARAM_INIT(value) = value
#else
#define NCURSES_PARAM_INIT(value) /*nothing*/
#endif

#if CPP_HAS_STATIC_CAST
#define STATIC_CAST(s) static_cast<s>
#else
#define STATIC_CAST(s) (s)
#endif

#ifndef NCURSES_CXX_IMPEXP
#define NCURSES_CXX_IMPEXP  /* nothing */
#endif

// Forward Declarations
class NCURSES_CXX_IMPEXP NCursesPanel;
class NCURSES_CXX_IMPEXP NCursesMenu;
class NCURSES_CXX_IMPEXP NCursesForm;

class NCURSES_CXX_IMPEXP NCursesException
{
public:
  const char *message;
  int errorno;

  NCursesException (const char* msg, int err)
    : message(msg), errorno (err)
    {};

  explicit NCursesException (const char* msg)
    : message(msg), errorno (E_SYSTEM_ERROR)
    {};

  NCursesException& operator=(const NCursesException& rhs)
  {
    message = rhs.message;
    errorno = rhs.errorno;
    return *this;
  }

  NCursesException(const NCursesException& rhs)
    : message(rhs.message), errorno(rhs.errorno)
  {
  }

  virtual const char *classname() const {
    return "NCursesWindow";
  }

  virtual ~NCursesException()
  {
  }
};

class NCURSES_CXX_IMPEXP NCursesPanelException : public NCursesException
{
public:
  const NCursesPanel* p;

  NCursesPanelException (const char *msg, int err) :
    NCursesException (msg, err),
    p (0)
    {};

  NCursesPanelException (const NCursesPanel* panel,
			 const char *msg,
			 int err) :
    NCursesException (msg, err),
    p (panel)
    {};

  explicit NCursesPanelException (int err) :
    NCursesException ("panel library error", err),
    p (0)
    {};

  NCursesPanelException (const NCursesPanel* panel,
			 int err) :
    NCursesException ("panel library error", err),
    p (panel)
    {};

  NCursesPanelException& operator=(const NCursesPanelException& rhs)
  {
    if (this != &rhs) {
      NCursesException::operator=(rhs);
      p = rhs.p;
    }
    return *this;
  }

  NCursesPanelException(const NCursesPanelException& rhs)
    : NCursesException(rhs), p(rhs.p)
  {
  }

  virtual const char *classname() const NCURSES_OVERRIDE {
    return "NCursesPanel";
  }

  virtual ~NCursesPanelException()
  {
  }
};

class NCURSES_CXX_IMPEXP NCursesMenuException : public NCursesException
{
public:
  const NCursesMenu* m;

  NCursesMenuException (const char *msg, int err) :
    NCursesException (msg, err),
    m (0)
    {};

  NCursesMenuException (const NCursesMenu* menu,
			const char *msg,
			int err) :
    NCursesException (msg, err),
    m (menu)
    {};

  explicit NCursesMenuException (int err) :
    NCursesException ("menu library error", err),
    m (0)
    {};

  NCursesMenuException (const NCursesMenu* menu,
			int err) :
    NCursesException ("menu library error", err),
    m (menu)
    {};

  NCursesMenuException& operator=(const NCursesMenuException& rhs)
  {
    if (this != &rhs) {
      NCursesException::operator=(rhs);
      m = rhs.m;
    }
    return *this;
  }

  NCursesMenuException(const NCursesMenuException& rhs)
    : NCursesException(rhs), m(rhs.m)
  {
  }

  virtual const char *classname() const NCURSES_OVERRIDE {
    return "NCursesMenu";
  }

  virtual ~NCursesMenuException()
  {
  }
};

class NCURSES_CXX_IMPEXP NCursesFormException : public NCursesException
{
public:
  const NCursesForm* f;

  NCursesFormException (const char *msg, int err) :
    NCursesException (msg, err),
    f (0)
    {};

  NCursesFormException (const NCursesForm* form,
			const char *msg,
			int err) :
    NCursesException (msg, err),
    f (form)
    {};

  explicit NCursesFormException (int err) :
    NCursesException ("form library error", err),
    f (0)
    {};

  NCursesFormException (const NCursesForm* form,
			int err) :
    NCursesException ("form library error", err),
    f (form)
    {};

  NCursesFormException& operator=(const NCursesFormException& rhs)
  {
    if (this != &rhs) {
      NCursesException::operator=(rhs);
      f = rhs.f;
    }
    return *this;
  }

  NCursesFormException(const NCursesFormException& rhs)
    : NCursesException(rhs), f(rhs.f)
  {
  }

  virtual const char *classname() const NCURSES_OVERRIDE {
    return "NCursesForm";
  }

  virtual ~NCursesFormException()
  {
  }
};

#if !((defined(__GNUG__) && defined(__EXCEPTIONS) && (__GNUG__ < 7)) || defined(__SUNPRO_CC))
#  if HAVE_IOSTREAM
#     include <iostream>
#     if IOSTREAM_NAMESPACE
using std::cerr;
using std::endl;
#     endif
#  else
#     include <iostream.h>
#  endif
#endif

inline void THROW(const NCursesException *e) {
#if defined(__GNUG__) && defined(__EXCEPTIONS)
#  if ((__GNUG__ <= 2) && (__GNUC_MINOR__ < 8))
      (*lib_error_handler)(e ? e->classname() : "", e ? e->message : "");
#  elif (__GNUG__ >= 7)
     // g++ 7.0 warns about deprecation, but lacks the predefined symbols
      ::endwin();
      std::cerr << "Found a problem - goodbye" << std::endl;
      exit(EXIT_FAILURE);
#  else
#    define CPP_HAS_TRY_CATCH 1
#  endif
#elif defined(__SUNPRO_CC)
#  if !defined(__SUNPRO_CC_COMPAT) || (__SUNPRO_CC_COMPAT < 5)
  genericerror(1, ((e != 0) ? (char *)(e->message) : ""));
#  else
#    define CPP_HAS_TRY_CATCH 1
#  endif
#else
  if (e)
    cerr << e->message << endl;
  exit(0);
#endif

#ifndef CPP_HAS_TRY_CATCH
#define CPP_HAS_TRY_CATCH 0
#define NCURSES_CPP_TRY		/* nothing */
#define NCURSES_CPP_CATCH(e)	if (false)
#define THROWS(s)		/* nothing */
#define THROW2(s,t)		/* nothing */
#elif CPP_HAS_TRY_CATCH
  throw *e;
#define NCURSES_CPP_TRY		try
#define NCURSES_CPP_CATCH(e)	catch(e)
#if defined(__cpp_noexcept_function_type) && (__cpp_noexcept_function_type >= 201510)
// C++17 deprecates the usage of throw().
#define THROWS(s)		/* nothing */
#define THROW2(s,t)		/* nothing */
#else
#define THROWS(s)		throw(s)
#define THROW2(s,t)		throw(s,t)
#endif
#endif
}

#endif /* NCURSES_ETIP_H_incl */
