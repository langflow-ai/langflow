/*
 * tclUnixPort.h --
 *
 *	This header file handles porting issues that occur because of
 *	differences between systems. It reads in UNIX-related header files and
 *	sets up UNIX-related macros for Tcl's UNIX core. It should be the only
 *	file that contains #ifdefs to handle different flavors of UNIX. This
 *	file sets up the union of all UNIX-related things needed by any of the
 *	Tcl core files. This file depends on configuration #defines such as
 *	NO_DIRENT_H that are set up by the "configure" script.
 *
 *	Much of the material in this file was originally contributed by Karl
 *	Lehenbauer, Mark Diekhans and Peter da Silva.
 *
 * Copyright (c) 1991-1994 The Regents of the University of California.
 * Copyright (c) 1994-1997 Sun Microsystems, Inc.
 *
 * See the file "license.terms" for information on usage and redistribution of
 * this file, and for a DISCLAIMER OF ALL WARRANTIES.
 */

#ifndef _TCLUNIXPORT
#define _TCLUNIXPORT

/*
 *---------------------------------------------------------------------------
 * The following sets of #includes and #ifdefs are required to get Tcl to
 * compile under the various flavors of unix.
 *---------------------------------------------------------------------------
 */

#include <errno.h>
#include <fcntl.h>
#ifdef HAVE_NET_ERRNO_H
#   include <net/errno.h>
#endif
#include <pwd.h>
#include <signal.h>
#ifdef HAVE_SYS_PARAM_H
#   include <sys/param.h>
#endif
#include <sys/types.h>
#ifdef USE_DIRENT2_H
#   include "../compat/dirent2.h"
#else
#ifdef NO_DIRENT_H
#   include "../compat/dirent.h"
#else
#   include <dirent.h>
#endif
#endif

/*
 *---------------------------------------------------------------------------
 * Parameterize for 64-bit filesystem support.
 *---------------------------------------------------------------------------
 */

#ifdef HAVE_STRUCT_DIRENT64
typedef struct dirent64		Tcl_DirEntry;
#   define TclOSreaddir		readdir64
#else
typedef struct dirent		Tcl_DirEntry;
#   define TclOSreaddir		readdir
#endif
#ifdef HAVE_DIR64
typedef DIR64			TclDIR;
#   define TclOSopendir		opendir64
#   define TclOSrewinddir	rewinddir64
#   define TclOSclosedir	closedir64
#else
typedef DIR			TclDIR;
#   define TclOSopendir		opendir
#   define TclOSrewinddir	rewinddir
#   define TclOSclosedir	closedir
#endif

#ifdef HAVE_TYPE_OFF64_T
typedef off64_t		Tcl_SeekOffset;
#   define TclOSseek		lseek64
#   define TclOSopen		open64
#else
typedef off_t		Tcl_SeekOffset;
#   define TclOSseek		lseek
#   define TclOSopen		open
#endif

#ifdef __CYGWIN__
#ifdef __cplusplus
extern "C" {
#endif
    /* Make some symbols available without including <windows.h> */
#   define DWORD unsigned int
#   define CP_UTF8 65001
#   define GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS 0x00000004
#   define HANDLE void *
#   define HINSTANCE void *
#   define SOCKET unsigned int
#   define WSAEWOULDBLOCK 10035
    typedef unsigned short WCHAR;
#ifdef __clang__
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wignored-attributes"
#endif
    __declspec(dllimport) extern __stdcall int GetModuleHandleExW(unsigned int, const void *, void *);
    __declspec(dllimport) extern __stdcall int GetModuleFileNameW(void *, const void *, int);
    __declspec(dllimport) extern __stdcall int WideCharToMultiByte(int, int, const void *, int,
	    char *, int, const char *, void *);
    __declspec(dllimport) extern __stdcall int MultiByteToWideChar(int, int, const char *, int,
	    WCHAR *, int);
    __declspec(dllimport) extern __stdcall void OutputDebugStringW(const WCHAR *);
    __declspec(dllimport) extern __stdcall int IsDebuggerPresent(void);
    __declspec(dllimport) extern __stdcall int GetLastError(void);
    __declspec(dllimport) extern __stdcall int GetFileAttributesW(const WCHAR *);
    __declspec(dllimport) extern __stdcall int SetFileAttributesW(const WCHAR *, int);
    __declspec(dllimport) extern int cygwin_conv_path(int, const void *, void *, int);
#ifdef __clang__
#pragma clang diagnostic pop
#endif
#   define timezone _timezone
    extern int TclOSstat(const char *name, void *statBuf);
    extern int TclOSlstat(const char *name, void *statBuf);
#ifdef __cplusplus
}
#endif
#elif defined(HAVE_STRUCT_STAT64) && !defined(__APPLE__)
#   define TclOSstat(name, buf) stat64(name, (struct stat64 *)buf)
#   define TclOSlstat(name,buf) lstat64(name, (struct stat64 *)buf)
#else
#   define TclOSstat(name, buf) stat(name, (struct stat *)buf)
#   define TclOSlstat(name, buf) lstat(name, (struct stat *)buf)
#endif

/*
 *---------------------------------------------------------------------------
 * Miscellaneous includes that might be missing.
 *---------------------------------------------------------------------------
 */

#include <sys/file.h>
#ifdef HAVE_SYS_SELECT_H
#   include <sys/select.h>
#endif
#include <sys/stat.h>
#ifdef TIME_WITH_SYS_TIME
#   include <sys/time.h>
#   include <time.h>
#else
#ifdef HAVE_SYS_TIME_H
#   include <sys/time.h>
#else
#   include <time.h>
#endif
#endif
#ifndef NO_SYS_WAIT_H
#   include <sys/wait.h>
#endif
#ifdef HAVE_INTTYPES_H
#   include <inttypes.h>
#endif
#include <limits.h>
#ifdef HAVE_STDINT_H
#   include <stdint.h>
#endif
#ifdef HAVE_UNISTD_H
#   include <unistd.h>
#else
#   include "../compat/unistd.h"
#endif

extern int TclUnixSetBlockingMode(int fd, int mode);

#include <utime.h>

/*
 *---------------------------------------------------------------------------
 * Socket support stuff: This likely needs more work to parameterize for each
 * system.
 *---------------------------------------------------------------------------
 */

#include <sys/socket.h>		/* struct sockaddr, SOCK_STREAM, ... */
#ifndef NO_UNAME
#   include <sys/utsname.h>	/* uname system call. */
#endif
#include <netinet/in.h>		/* struct in_addr, struct sockaddr_in */
#include <arpa/inet.h>		/* inet_ntoa() */
#include <netdb.h>		/* getaddrinfo() */
#ifdef NEED_FAKE_RFC2553
# include "../compat/fake-rfc2553.h"
#endif

/*
 *---------------------------------------------------------------------------
 * Some platforms (e.g. SunOS) don't define FLT_MAX and FLT_MIN, so we look
 * for an alternative definition. If no other alternative is available we use
 * a reasonable guess.
 *---------------------------------------------------------------------------
 */

#ifndef NO_FLOAT_H
#   include <float.h>
#else
#ifndef NO_VALUES_H
#   include <values.h>
#endif
#endif

#ifndef FLT_MAX
#   ifdef MAXFLOAT
#	define FLT_MAX	MAXFLOAT
#   else
#	define FLT_MAX	3.402823466E+38F
#   endif
#endif
#ifndef FLT_MIN
#   ifdef MINFLOAT
#	define FLT_MIN	MINFLOAT
#   else
#	define FLT_MIN	1.175494351E-38F
#   endif
#endif

/*
 *---------------------------------------------------------------------------
 * NeXT doesn't define O_NONBLOCK, so #define it here if necessary.
 *---------------------------------------------------------------------------
 */

#ifndef O_NONBLOCK
#   define O_NONBLOCK 0x80
#endif

/*
 *---------------------------------------------------------------------------
 * The type of the status returned by wait varies from UNIX system to UNIX
 * system. The macro below defines it:
 *---------------------------------------------------------------------------
 */

#ifdef _AIX
#   define WAIT_STATUS_TYPE	pid_t
#else
#ifndef NO_UNION_WAIT
#   define WAIT_STATUS_TYPE	union wait
#else
#   define WAIT_STATUS_TYPE	int
#endif
#endif

/*
 *---------------------------------------------------------------------------
 * Supply definitions for macros to query wait status, if not already defined
 * in header files above.
 *---------------------------------------------------------------------------
 */

#ifndef WIFEXITED
#   define WIFEXITED(stat)	(((*((int *) &(stat))) & 0xFF) == 0)
#endif

#ifndef WEXITSTATUS
#   define WEXITSTATUS(stat)	(((*((int *) &(stat))) >> 8) & 0xFF)
#endif

#ifndef WIFSIGNALED
#   define WIFSIGNALED(stat) \
	(((*((int *) &(stat)))) && ((*((int *) &(stat))) \
		== ((*((int *) &(stat))) & 0x00FF)))
#endif

#ifndef WTERMSIG
#   define WTERMSIG(stat)	((*((int *) &(stat))) & 0x7F)
#endif

#ifndef WIFSTOPPED
#   define WIFSTOPPED(stat)	(((*((int *) &(stat))) & 0xFF) == 0177)
#endif

#ifndef WSTOPSIG
#   define WSTOPSIG(stat)	(((*((int *) &(stat))) >> 8) & 0xFF)
#endif

/*
 *---------------------------------------------------------------------------
 * Define constants for waitpid() system call if they aren't defined by a
 * system header file.
 *---------------------------------------------------------------------------
 */

#ifndef WNOHANG
#   define WNOHANG 1
#endif
#ifndef WUNTRACED
#   define WUNTRACED 2
#endif

/*
 *---------------------------------------------------------------------------
 * Supply macros for seek offsets, if they're not already provided by an
 * include file.
 *---------------------------------------------------------------------------
 */

#ifndef SEEK_SET
#   define SEEK_SET 0
#endif
#ifndef SEEK_CUR
#   define SEEK_CUR 1
#endif
#ifndef SEEK_END
#   define SEEK_END 2
#endif

/*
 *---------------------------------------------------------------------------
 * The stuff below is needed by the "time" command. If this system has no
 * gettimeofday call, then must use times() instead.
 *---------------------------------------------------------------------------
 */

#ifdef NO_GETTOD
#   include <sys/times.h>
#else
#   ifdef HAVE_BSDGETTIMEOFDAY
#	define gettimeofday BSDgettimeofday
#   endif
#endif

#ifdef GETTOD_NOT_DECLARED
extern int	gettimeofday(struct timeval *tp,
			    struct timezone *tzp);
#endif

/*
 *---------------------------------------------------------------------------
 * Define access mode constants if they aren't already defined.
 *---------------------------------------------------------------------------
 */

#ifndef F_OK
#   define F_OK		00
#endif
#ifndef X_OK
#   define X_OK		01
#endif
#ifndef W_OK
#   define W_OK		02
#endif
#ifndef R_OK
#   define R_OK		04
#endif

/*
 *---------------------------------------------------------------------------
 * Define FD_CLOEEXEC (the close-on-exec flag bit) if it isn't already
 * defined.
 *---------------------------------------------------------------------------
 */

#ifndef FD_CLOEXEC
#   define FD_CLOEXEC	1
#endif

/*
 *---------------------------------------------------------------------------
 * On systems without symbolic links (i.e. S_IFLNK isn't defined) define
 * "lstat" to use "stat" instead.
 *---------------------------------------------------------------------------
 */

#ifndef S_IFLNK
#   undef TclOSlstat
#   define lstat	stat
#   define lstat64	stat64
#   define TclOSlstat	TclOSstat
#endif

/*
 *---------------------------------------------------------------------------
 * Define macros to query file type bits, if they're not already defined.
 *---------------------------------------------------------------------------
 */

#ifndef S_ISREG
#   ifdef S_IFREG
#	define S_ISREG(m)	(((m) & S_IFMT) == S_IFREG)
#   else
#	define S_ISREG(m)	0
#   endif
#endif /* !S_ISREG */
#ifndef S_ISDIR
#   ifdef S_IFDIR
#	define S_ISDIR(m)	(((m) & S_IFMT) == S_IFDIR)
#   else
#	define S_ISDIR(m)	0
#   endif
#endif /* !S_ISDIR */
#ifndef S_ISCHR
#   ifdef S_IFCHR
#	define S_ISCHR(m)	(((m) & S_IFMT) == S_IFCHR)
#   else
#	define S_ISCHR(m)	0
#   endif
#endif /* !S_ISCHR */

#ifndef S_ISBLK
#   ifdef S_IFBLK
#	define S_ISBLK(m)	(((m) & S_IFMT) == S_IFBLK)
#   else
#	define S_ISBLK(m)	0
#   endif
#endif /* !S_ISBLK */

#ifndef S_ISFIFO
#   ifdef S_IFIFO
#	define S_ISFIFO(m)	(((m) & S_IFMT) == S_IFIFO)
#   else
#	define S_ISFIFO(m)	0
#   endif
#endif /* !S_ISFIFO */

#ifndef S_ISLNK
#   ifdef S_IFLNK
#	define S_ISLNK(m)	(((m) & S_IFMT) == S_IFLNK)
#   else
#	define S_ISLNK(m)	0
#   endif
#endif /* !S_ISLNK */

#ifndef S_ISSOCK
#   ifdef S_IFSOCK
#	define S_ISSOCK(m)	(((m) & S_IFMT) == S_IFSOCK)
#   else
#	define S_ISSOCK(m)	0
#   endif
#endif /* !S_ISSOCK */

/*
 *---------------------------------------------------------------------------
 * Make sure that MAXPATHLEN and MAXNAMLEN are defined.
 *---------------------------------------------------------------------------
 */

#ifndef MAXPATHLEN
#   ifdef PATH_MAX
#	define MAXPATHLEN	PATH_MAX
#   else
#	define MAXPATHLEN	2048
#   endif
#endif

#ifndef MAXNAMLEN
#   ifdef NAME_MAX
#	define MAXNAMLEN	NAME_MAX
#   else
#	define MAXNAMLEN	255
#   endif
#endif

/*
 *---------------------------------------------------------------------------
 * The following macro defines the type of the mask arguments to select:
 *---------------------------------------------------------------------------
 */

#ifndef NO_FD_SET
#   define SELECT_MASK	fd_set
#else /* NO_FD_SET */
#   ifndef _AIX
	typedef long	fd_mask;
#   endif /* !AIX */
#   if defined(_IBMR2)
#	define SELECT_MASK	void
#   else /* !defined(_IBMR2) */
#	define SELECT_MASK	int
#   endif /* defined(_IBMR2) */
#endif /* !NO_FD_SET */

/*
 *---------------------------------------------------------------------------
 * Define "NBBY" (number of bits per byte) if it's not already defined.
 *---------------------------------------------------------------------------
 */

#ifndef NBBY
#   define NBBY		8
#endif

/*
 *---------------------------------------------------------------------------
 * The following macro defines the number of fd_masks in an fd_set:
 *---------------------------------------------------------------------------
 */

#ifndef FD_SETSIZE
#   ifdef OPEN_MAX
#	define FD_SETSIZE	OPEN_MAX
#   else
#	define FD_SETSIZE	256
#   endif
#endif /* FD_SETSIZE */

#ifndef howmany
#   define howmany(x, y)	(((x)+((y)-1))/(y))
#endif /* !defined(howmany) */

#ifndef NFDBITS
#   define NFDBITS	NBBY*sizeof(fd_mask)
#endif /* NFDBITS */

#define MASK_SIZE	howmany(FD_SETSIZE, NFDBITS)

/*
 *---------------------------------------------------------------------------
 * Not all systems declare the errno variable in errno.h, so this file does it
 * explicitly. The list of system error messages also isn't generally declared
 * in a header file anywhere.
 *---------------------------------------------------------------------------
 */

#ifdef NO_ERRNO
extern int errno;
#endif /* NO_ERRNO */

/*
 *---------------------------------------------------------------------------
 * Not all systems declare all the errors that Tcl uses! Provide some
 * work-arounds...
 *---------------------------------------------------------------------------
 */

#ifndef EOVERFLOW
#   ifdef EFBIG
#	define EOVERFLOW	EFBIG
#   else /* !EFBIG */
#	define EOVERFLOW	EINVAL
#   endif /* EFBIG */
#endif /* EOVERFLOW */

/*
 *---------------------------------------------------------------------------
 * Variables provided by the C library:
 *---------------------------------------------------------------------------
 */

#if defined(__APPLE__) && defined(__DYNAMIC__)
#   include <crt_externs.h>
#   define environ	(*_NSGetEnviron())
#   define USE_PUTENV	1
#else
#   if defined(_sgi) || defined(__sgi)
#	define environ	_environ
#   endif
extern char **		environ;
#endif

/*
 *---------------------------------------------------------------------------
 * Darwin specifc configure overrides.
 *---------------------------------------------------------------------------
 */

#ifdef __APPLE__

/*
 *---------------------------------------------------------------------------
 * Support for fat compiles: configure runs only once for multiple architectures
 *---------------------------------------------------------------------------
 */

#   if defined(__LP64__) && defined (NO_COREFOUNDATION_64)
#	undef HAVE_COREFOUNDATION
#   endif /* __LP64__ && NO_COREFOUNDATION_64 */
#   include <sys/cdefs.h>
#   ifdef __DARWIN_UNIX03
#	if __DARWIN_UNIX03
#	    undef HAVE_PUTENV_THAT_COPIES
#	else
#	    define HAVE_PUTENV_THAT_COPIES	1
#	endif
#   endif /* __DARWIN_UNIX03 */

/*
 *---------------------------------------------------------------------------
 * Include AvailabilityMacros.h here (when available) to ensure any symbolic
 * MAC_OS_X_VERSION_* constants passed on the command line are translated.
 *---------------------------------------------------------------------------
 */

#   ifdef HAVE_AVAILABILITYMACROS_H
#	include <AvailabilityMacros.h>
#   endif

/*
 *---------------------------------------------------------------------------
 * Support for weak import.
 *---------------------------------------------------------------------------
 */

#   ifdef HAVE_WEAK_IMPORT
#	if !defined(HAVE_AVAILABILITYMACROS_H) || !defined(MAC_OS_X_VERSION_MIN_REQUIRED)
#	    undef HAVE_WEAK_IMPORT
#	else
#	    ifndef WEAK_IMPORT_ATTRIBUTE
#		define WEAK_IMPORT_ATTRIBUTE	__attribute__((weak_import))
#	    endif
#	endif
#   endif /* HAVE_WEAK_IMPORT */

/*
 *---------------------------------------------------------------------------
 * Support for MAC_OS_X_VERSION_MAX_ALLOWED define from AvailabilityMacros.h:
 * only use API available in the indicated OS version or earlier.
 *---------------------------------------------------------------------------
 */

#   ifdef MAC_OS_X_VERSION_MAX_ALLOWED
#	if MAC_OS_X_VERSION_MAX_ALLOWED < 1050 && defined(__LP64__)
#	    undef HAVE_COREFOUNDATION
#	endif
#	if MAC_OS_X_VERSION_MAX_ALLOWED < 1040
#	    undef HAVE_OSSPINLOCKLOCK
#	    undef HAVE_PTHREAD_ATFORK
#	    undef HAVE_COPYFILE
#	endif
#	if MAC_OS_X_VERSION_MAX_ALLOWED < 1030
#	    ifdef TCL_THREADS
		/* prior to 10.3, realpath is not threadsafe, c.f. bug 711232 */
#		define NO_REALPATH 1
#	    endif
#	    undef HAVE_LANGINFO
#	endif
#   endif /* MAC_OS_X_VERSION_MAX_ALLOWED */
#   if defined(HAVE_COREFOUNDATION) && defined(__LP64__) && \
	    defined(HAVE_WEAK_IMPORT) && MAC_OS_X_VERSION_MIN_REQUIRED < 1050
#	warning "Weak import of 64-bit CoreFoundation is not supported, will not run on Mac OS X < 10.5."
#   endif
    /*
     * For now, test exec-17.1 fails (I/O setup after closing stdout) with
     * posix_spawnp(), but the classic implementation (based on fork()+execvp())
     * works well under macOS.
     */
#   undef HAVE_POSIX_SPAWNP
#   undef HAVE_VFORK
#endif /* __APPLE__ */

/*
 *---------------------------------------------------------------------------
 * The following macros and declarations represent the interface between
 * generic and unix-specific parts of Tcl. Some of the macros may override
 * functions declared in tclInt.h.
 *---------------------------------------------------------------------------
 */

/*
 * The default platform eol translation on Unix is TCL_TRANSLATE_LF.
 */

#ifdef DJGPP
#define	TCL_PLATFORM_TRANSLATION	TCL_TRANSLATE_CRLF
typedef int socklen_t;
#else
#define	TCL_PLATFORM_TRANSLATION	TCL_TRANSLATE_LF
#endif

/*
 *---------------------------------------------------------------------------
 * The following macros have trivial definitions, allowing generic code to
 * address platform-specific issues.
 *---------------------------------------------------------------------------
 */

#define TclpReleaseFile(file)	/* Nothing. */

/*
 *---------------------------------------------------------------------------
 * The following defines wrap the system memory allocation routines.
 *---------------------------------------------------------------------------
 */

#define TclpSysAlloc(size, isBin)	malloc((size_t)(size))
#define TclpSysFree(ptr)		free((char *)(ptr))
#define TclpSysRealloc(ptr, size)	realloc((char *)(ptr), (size_t)(size))

/*
 *---------------------------------------------------------------------------
 * The following macros and declaration wrap the C runtime library functions.
 *---------------------------------------------------------------------------
 */

#define TclpExit	exit

#ifdef TCL_THREADS
#   include <pthread.h>
#endif /* TCL_THREADS */

/* FIXME - Hyper-enormous platform assumption! */
#ifndef AF_INET6
#   define AF_INET6	10
#endif

/*
 *---------------------------------------------------------------------------
 * Set of MT-safe implementations of some known-to-be-MT-unsafe library calls.
 * Instead of returning pointers to the static storage, those return pointers
 * to the TSD data.
 *---------------------------------------------------------------------------
 */

#include <pwd.h>
#include <grp.h>

extern struct passwd *	TclpGetPwNam(const char *name);
extern struct group *	TclpGetGrNam(const char *name);
extern struct passwd *	TclpGetPwUid(uid_t uid);
extern struct group *	TclpGetGrGid(gid_t gid);
extern struct hostent *	TclpGetHostByName(const char *name);
extern struct hostent *	TclpGetHostByAddr(const char *addr,
				    int length, int type);
extern void *TclpMakeTcpClientChannelMode(
				    void *tcpSocket, int mode);

#endif /* _TCLUNIXPORT */

/*
 * Local Variables:
 * mode: c
 * c-basic-offset: 4
 * fill-column: 78
 * End:
 */
