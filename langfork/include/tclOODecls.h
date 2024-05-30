/*
 * This file is (mostly) automatically generated from tclOO.decls.
 */

#ifndef _TCLOODECLS
#define _TCLOODECLS

#ifndef TCLAPI
#   ifdef BUILD_tcl
#	define TCLAPI extern DLLEXPORT
#   else
#	define TCLAPI extern DLLIMPORT
#   endif
#endif

#ifdef USE_TCL_STUBS
#   undef USE_TCLOO_STUBS
#   define USE_TCLOO_STUBS
#endif

/* !BEGIN!: Do not edit below this line. */

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Exported function declarations:
 */

/* 0 */
TCLAPI Tcl_Object	Tcl_CopyObjectInstance(Tcl_Interp *interp,
				Tcl_Object sourceObject,
				const char *targetName,
				const char *targetNamespaceName);
/* 1 */
TCLAPI Tcl_Object	Tcl_GetClassAsObject(Tcl_Class clazz);
/* 2 */
TCLAPI Tcl_Class	Tcl_GetObjectAsClass(Tcl_Object object);
/* 3 */
TCLAPI Tcl_Command	Tcl_GetObjectCommand(Tcl_Object object);
/* 4 */
TCLAPI Tcl_Object	Tcl_GetObjectFromObj(Tcl_Interp *interp,
				Tcl_Obj *objPtr);
/* 5 */
TCLAPI Tcl_Namespace *	Tcl_GetObjectNamespace(Tcl_Object object);
/* 6 */
TCLAPI Tcl_Class	Tcl_MethodDeclarerClass(Tcl_Method method);
/* 7 */
TCLAPI Tcl_Object	Tcl_MethodDeclarerObject(Tcl_Method method);
/* 8 */
TCLAPI int		Tcl_MethodIsPublic(Tcl_Method method);
/* 9 */
TCLAPI int		Tcl_MethodIsType(Tcl_Method method,
				const Tcl_MethodType *typePtr,
				void **clientDataPtr);
/* 10 */
TCLAPI Tcl_Obj *	Tcl_MethodName(Tcl_Method method);
/* 11 */
TCLAPI Tcl_Method	Tcl_NewInstanceMethod(Tcl_Interp *interp,
				Tcl_Object object, Tcl_Obj *nameObj,
				int isPublic, const Tcl_MethodType *typePtr,
				void *clientData);
/* 12 */
TCLAPI Tcl_Method	Tcl_NewMethod(Tcl_Interp *interp, Tcl_Class cls,
				Tcl_Obj *nameObj, int isPublic,
				const Tcl_MethodType *typePtr,
				void *clientData);
/* 13 */
TCLAPI Tcl_Object	Tcl_NewObjectInstance(Tcl_Interp *interp,
				Tcl_Class cls, const char *nameStr,
				const char *nsNameStr, int objc,
				Tcl_Obj *const *objv, int skip);
/* 14 */
TCLAPI int		Tcl_ObjectDeleted(Tcl_Object object);
/* 15 */
TCLAPI int		Tcl_ObjectContextIsFiltering(
				Tcl_ObjectContext context);
/* 16 */
TCLAPI Tcl_Method	Tcl_ObjectContextMethod(Tcl_ObjectContext context);
/* 17 */
TCLAPI Tcl_Object	Tcl_ObjectContextObject(Tcl_ObjectContext context);
/* 18 */
TCLAPI int		Tcl_ObjectContextSkippedArgs(
				Tcl_ObjectContext context);
/* 19 */
TCLAPI void *		Tcl_ClassGetMetadata(Tcl_Class clazz,
				const Tcl_ObjectMetadataType *typePtr);
/* 20 */
TCLAPI void		Tcl_ClassSetMetadata(Tcl_Class clazz,
				const Tcl_ObjectMetadataType *typePtr,
				void *metadata);
/* 21 */
TCLAPI void *		Tcl_ObjectGetMetadata(Tcl_Object object,
				const Tcl_ObjectMetadataType *typePtr);
/* 22 */
TCLAPI void		Tcl_ObjectSetMetadata(Tcl_Object object,
				const Tcl_ObjectMetadataType *typePtr,
				void *metadata);
/* 23 */
TCLAPI int		Tcl_ObjectContextInvokeNext(Tcl_Interp *interp,
				Tcl_ObjectContext context, int objc,
				Tcl_Obj *const *objv, int skip);
/* 24 */
TCLAPI Tcl_ObjectMapMethodNameProc * Tcl_ObjectGetMethodNameMapper(
				Tcl_Object object);
/* 25 */
TCLAPI void		Tcl_ObjectSetMethodNameMapper(Tcl_Object object,
				Tcl_ObjectMapMethodNameProc *mapMethodNameProc);
/* 26 */
TCLAPI void		Tcl_ClassSetConstructor(Tcl_Interp *interp,
				Tcl_Class clazz, Tcl_Method method);
/* 27 */
TCLAPI void		Tcl_ClassSetDestructor(Tcl_Interp *interp,
				Tcl_Class clazz, Tcl_Method method);
/* 28 */
TCLAPI Tcl_Obj *	Tcl_GetObjectName(Tcl_Interp *interp,
				Tcl_Object object);
/* Slot 29 is reserved */
/* Slot 30 is reserved */
/* Slot 31 is reserved */
/* Slot 32 is reserved */
/* Slot 33 is reserved */
/* 34 */
TCLAPI void		TclOOUnusedStubEntry(void);

typedef struct {
    const struct TclOOIntStubs *tclOOIntStubs;
} TclOOStubHooks;

typedef struct TclOOStubs {
    int magic;
    const TclOOStubHooks *hooks;

    Tcl_Object (*tcl_CopyObjectInstance) (Tcl_Interp *interp, Tcl_Object sourceObject, const char *targetName, const char *targetNamespaceName); /* 0 */
    Tcl_Object (*tcl_GetClassAsObject) (Tcl_Class clazz); /* 1 */
    Tcl_Class (*tcl_GetObjectAsClass) (Tcl_Object object); /* 2 */
    Tcl_Command (*tcl_GetObjectCommand) (Tcl_Object object); /* 3 */
    Tcl_Object (*tcl_GetObjectFromObj) (Tcl_Interp *interp, Tcl_Obj *objPtr); /* 4 */
    Tcl_Namespace * (*tcl_GetObjectNamespace) (Tcl_Object object); /* 5 */
    Tcl_Class (*tcl_MethodDeclarerClass) (Tcl_Method method); /* 6 */
    Tcl_Object (*tcl_MethodDeclarerObject) (Tcl_Method method); /* 7 */
    int (*tcl_MethodIsPublic) (Tcl_Method method); /* 8 */
    int (*tcl_MethodIsType) (Tcl_Method method, const Tcl_MethodType *typePtr, void **clientDataPtr); /* 9 */
    Tcl_Obj * (*tcl_MethodName) (Tcl_Method method); /* 10 */
    Tcl_Method (*tcl_NewInstanceMethod) (Tcl_Interp *interp, Tcl_Object object, Tcl_Obj *nameObj, int isPublic, const Tcl_MethodType *typePtr, void *clientData); /* 11 */
    Tcl_Method (*tcl_NewMethod) (Tcl_Interp *interp, Tcl_Class cls, Tcl_Obj *nameObj, int isPublic, const Tcl_MethodType *typePtr, void *clientData); /* 12 */
    Tcl_Object (*tcl_NewObjectInstance) (Tcl_Interp *interp, Tcl_Class cls, const char *nameStr, const char *nsNameStr, int objc, Tcl_Obj *const *objv, int skip); /* 13 */
    int (*tcl_ObjectDeleted) (Tcl_Object object); /* 14 */
    int (*tcl_ObjectContextIsFiltering) (Tcl_ObjectContext context); /* 15 */
    Tcl_Method (*tcl_ObjectContextMethod) (Tcl_ObjectContext context); /* 16 */
    Tcl_Object (*tcl_ObjectContextObject) (Tcl_ObjectContext context); /* 17 */
    int (*tcl_ObjectContextSkippedArgs) (Tcl_ObjectContext context); /* 18 */
    void * (*tcl_ClassGetMetadata) (Tcl_Class clazz, const Tcl_ObjectMetadataType *typePtr); /* 19 */
    void (*tcl_ClassSetMetadata) (Tcl_Class clazz, const Tcl_ObjectMetadataType *typePtr, void *metadata); /* 20 */
    void * (*tcl_ObjectGetMetadata) (Tcl_Object object, const Tcl_ObjectMetadataType *typePtr); /* 21 */
    void (*tcl_ObjectSetMetadata) (Tcl_Object object, const Tcl_ObjectMetadataType *typePtr, void *metadata); /* 22 */
    int (*tcl_ObjectContextInvokeNext) (Tcl_Interp *interp, Tcl_ObjectContext context, int objc, Tcl_Obj *const *objv, int skip); /* 23 */
    Tcl_ObjectMapMethodNameProc * (*tcl_ObjectGetMethodNameMapper) (Tcl_Object object); /* 24 */
    void (*tcl_ObjectSetMethodNameMapper) (Tcl_Object object, Tcl_ObjectMapMethodNameProc *mapMethodNameProc); /* 25 */
    void (*tcl_ClassSetConstructor) (Tcl_Interp *interp, Tcl_Class clazz, Tcl_Method method); /* 26 */
    void (*tcl_ClassSetDestructor) (Tcl_Interp *interp, Tcl_Class clazz, Tcl_Method method); /* 27 */
    Tcl_Obj * (*tcl_GetObjectName) (Tcl_Interp *interp, Tcl_Object object); /* 28 */
    void (*reserved29)(void);
    void (*reserved30)(void);
    void (*reserved31)(void);
    void (*reserved32)(void);
    void (*reserved33)(void);
    void (*tclOOUnusedStubEntry) (void); /* 34 */
} TclOOStubs;

extern const TclOOStubs *tclOOStubsPtr;

#ifdef __cplusplus
}
#endif

#if defined(USE_TCLOO_STUBS)

/*
 * Inline function declarations:
 */

#define Tcl_CopyObjectInstance \
	(tclOOStubsPtr->tcl_CopyObjectInstance) /* 0 */
#define Tcl_GetClassAsObject \
	(tclOOStubsPtr->tcl_GetClassAsObject) /* 1 */
#define Tcl_GetObjectAsClass \
	(tclOOStubsPtr->tcl_GetObjectAsClass) /* 2 */
#define Tcl_GetObjectCommand \
	(tclOOStubsPtr->tcl_GetObjectCommand) /* 3 */
#define Tcl_GetObjectFromObj \
	(tclOOStubsPtr->tcl_GetObjectFromObj) /* 4 */
#define Tcl_GetObjectNamespace \
	(tclOOStubsPtr->tcl_GetObjectNamespace) /* 5 */
#define Tcl_MethodDeclarerClass \
	(tclOOStubsPtr->tcl_MethodDeclarerClass) /* 6 */
#define Tcl_MethodDeclarerObject \
	(tclOOStubsPtr->tcl_MethodDeclarerObject) /* 7 */
#define Tcl_MethodIsPublic \
	(tclOOStubsPtr->tcl_MethodIsPublic) /* 8 */
#define Tcl_MethodIsType \
	(tclOOStubsPtr->tcl_MethodIsType) /* 9 */
#define Tcl_MethodName \
	(tclOOStubsPtr->tcl_MethodName) /* 10 */
#define Tcl_NewInstanceMethod \
	(tclOOStubsPtr->tcl_NewInstanceMethod) /* 11 */
#define Tcl_NewMethod \
	(tclOOStubsPtr->tcl_NewMethod) /* 12 */
#define Tcl_NewObjectInstance \
	(tclOOStubsPtr->tcl_NewObjectInstance) /* 13 */
#define Tcl_ObjectDeleted \
	(tclOOStubsPtr->tcl_ObjectDeleted) /* 14 */
#define Tcl_ObjectContextIsFiltering \
	(tclOOStubsPtr->tcl_ObjectContextIsFiltering) /* 15 */
#define Tcl_ObjectContextMethod \
	(tclOOStubsPtr->tcl_ObjectContextMethod) /* 16 */
#define Tcl_ObjectContextObject \
	(tclOOStubsPtr->tcl_ObjectContextObject) /* 17 */
#define Tcl_ObjectContextSkippedArgs \
	(tclOOStubsPtr->tcl_ObjectContextSkippedArgs) /* 18 */
#define Tcl_ClassGetMetadata \
	(tclOOStubsPtr->tcl_ClassGetMetadata) /* 19 */
#define Tcl_ClassSetMetadata \
	(tclOOStubsPtr->tcl_ClassSetMetadata) /* 20 */
#define Tcl_ObjectGetMetadata \
	(tclOOStubsPtr->tcl_ObjectGetMetadata) /* 21 */
#define Tcl_ObjectSetMetadata \
	(tclOOStubsPtr->tcl_ObjectSetMetadata) /* 22 */
#define Tcl_ObjectContextInvokeNext \
	(tclOOStubsPtr->tcl_ObjectContextInvokeNext) /* 23 */
#define Tcl_ObjectGetMethodNameMapper \
	(tclOOStubsPtr->tcl_ObjectGetMethodNameMapper) /* 24 */
#define Tcl_ObjectSetMethodNameMapper \
	(tclOOStubsPtr->tcl_ObjectSetMethodNameMapper) /* 25 */
#define Tcl_ClassSetConstructor \
	(tclOOStubsPtr->tcl_ClassSetConstructor) /* 26 */
#define Tcl_ClassSetDestructor \
	(tclOOStubsPtr->tcl_ClassSetDestructor) /* 27 */
#define Tcl_GetObjectName \
	(tclOOStubsPtr->tcl_GetObjectName) /* 28 */
/* Slot 29 is reserved */
/* Slot 30 is reserved */
/* Slot 31 is reserved */
/* Slot 32 is reserved */
/* Slot 33 is reserved */
#define TclOOUnusedStubEntry \
	(tclOOStubsPtr->tclOOUnusedStubEntry) /* 34 */

#endif /* defined(USE_TCLOO_STUBS) */

/* !END!: Do not edit above this line. */

#undef TclOOUnusedStubEntry

#endif /* _TCLOODECLS */
