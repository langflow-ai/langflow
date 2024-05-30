/*
 * This file is (mostly) automatically generated from itcl.decls.
 */

#ifndef _ITCLDECLS
#define _ITCLDECLS

#if defined(USE_ITCL_STUBS)

ITCLAPI const char *Itcl_InitStubs(
	Tcl_Interp *, const char *version, int exact);
#else

#define Itcl_InitStubs(interp, version, exact) Tcl_PkgRequireEx(interp,"itcl",version,exact,NULL)

#endif


/* !BEGIN!: Do not edit below this line. */

#define ITCL_STUBS_EPOCH 0
#define ITCL_STUBS_REVISION 152

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Exported function declarations:
 */

/* Slot 0 is reserved */
/* Slot 1 is reserved */
/* 2 */
ITCLAPI int		Itcl_RegisterC(Tcl_Interp *interp, const char *name,
				Tcl_CmdProc *proc, void *clientData,
				Tcl_CmdDeleteProc *deleteProc);
/* 3 */
ITCLAPI int		Itcl_RegisterObjC(Tcl_Interp *interp,
				const char *name, Tcl_ObjCmdProc *proc,
				void *clientData,
				Tcl_CmdDeleteProc *deleteProc);
/* 4 */
ITCLAPI int		Itcl_FindC(Tcl_Interp *interp, const char *name,
				Tcl_CmdProc **argProcPtr,
				Tcl_ObjCmdProc **objProcPtr, void **cDataPtr);
/* 5 */
ITCLAPI void		Itcl_InitStack(Itcl_Stack *stack);
/* 6 */
ITCLAPI void		Itcl_DeleteStack(Itcl_Stack *stack);
/* 7 */
ITCLAPI void		Itcl_PushStack(void *cdata, Itcl_Stack *stack);
/* 8 */
ITCLAPI void *		Itcl_PopStack(Itcl_Stack *stack);
/* 9 */
ITCLAPI void *		Itcl_PeekStack(Itcl_Stack *stack);
/* 10 */
ITCLAPI void *		Itcl_GetStackValue(Itcl_Stack *stack, Tcl_Size pos);
/* 11 */
ITCLAPI void		Itcl_InitList(Itcl_List *listPtr);
/* 12 */
ITCLAPI void		Itcl_DeleteList(Itcl_List *listPtr);
/* 13 */
ITCLAPI Itcl_ListElem *	 Itcl_CreateListElem(Itcl_List *listPtr);
/* 14 */
ITCLAPI Itcl_ListElem *	 Itcl_DeleteListElem(Itcl_ListElem *elemPtr);
/* 15 */
ITCLAPI Itcl_ListElem *	 Itcl_InsertList(Itcl_List *listPtr, void *val);
/* 16 */
ITCLAPI Itcl_ListElem *	 Itcl_InsertListElem(Itcl_ListElem *pos, void *val);
/* 17 */
ITCLAPI Itcl_ListElem *	 Itcl_AppendList(Itcl_List *listPtr, void *val);
/* 18 */
ITCLAPI Itcl_ListElem *	 Itcl_AppendListElem(Itcl_ListElem *pos, void *val);
/* 19 */
ITCLAPI void		Itcl_SetListValue(Itcl_ListElem *elemPtr, void *val);
/* 20 */
ITCLAPI void		Itcl_EventuallyFree(void *cdata, Tcl_FreeProc *fproc);
/* 21 */
ITCLAPI void		Itcl_PreserveData(void *cdata);
/* 22 */
ITCLAPI void		Itcl_ReleaseData(void *cdata);
/* 23 */
ITCLAPI Itcl_InterpState Itcl_SaveInterpState(Tcl_Interp *interp, int status);
/* 24 */
ITCLAPI int		Itcl_RestoreInterpState(Tcl_Interp *interp,
				Itcl_InterpState state);
/* 25 */
ITCLAPI void		Itcl_DiscardInterpState(Itcl_InterpState state);
/* 26 */
ITCLAPI void *		Itcl_Alloc(size_t size);
/* 27 */
ITCLAPI void		Itcl_Free(void *ptr);

typedef struct {
    const struct ItclIntStubs *itclIntStubs;
} ItclStubHooks;

typedef struct ItclStubs {
    int magic;
    int epoch;
    int revision;
    const ItclStubHooks *hooks;

    void (*reserved0)(void);
    void (*reserved1)(void);
    int (*itcl_RegisterC) (Tcl_Interp *interp, const char *name, Tcl_CmdProc *proc, void *clientData, Tcl_CmdDeleteProc *deleteProc); /* 2 */
    int (*itcl_RegisterObjC) (Tcl_Interp *interp, const char *name, Tcl_ObjCmdProc *proc, void *clientData, Tcl_CmdDeleteProc *deleteProc); /* 3 */
    int (*itcl_FindC) (Tcl_Interp *interp, const char *name, Tcl_CmdProc **argProcPtr, Tcl_ObjCmdProc **objProcPtr, void **cDataPtr); /* 4 */
    void (*itcl_InitStack) (Itcl_Stack *stack); /* 5 */
    void (*itcl_DeleteStack) (Itcl_Stack *stack); /* 6 */
    void (*itcl_PushStack) (void *cdata, Itcl_Stack *stack); /* 7 */
    void * (*itcl_PopStack) (Itcl_Stack *stack); /* 8 */
    void * (*itcl_PeekStack) (Itcl_Stack *stack); /* 9 */
    void * (*itcl_GetStackValue) (Itcl_Stack *stack, Tcl_Size pos); /* 10 */
    void (*itcl_InitList) (Itcl_List *listPtr); /* 11 */
    void (*itcl_DeleteList) (Itcl_List *listPtr); /* 12 */
    Itcl_ListElem * (*itcl_CreateListElem) (Itcl_List *listPtr); /* 13 */
    Itcl_ListElem * (*itcl_DeleteListElem) (Itcl_ListElem *elemPtr); /* 14 */
    Itcl_ListElem * (*itcl_InsertList) (Itcl_List *listPtr, void *val); /* 15 */
    Itcl_ListElem * (*itcl_InsertListElem) (Itcl_ListElem *pos, void *val); /* 16 */
    Itcl_ListElem * (*itcl_AppendList) (Itcl_List *listPtr, void *val); /* 17 */
    Itcl_ListElem * (*itcl_AppendListElem) (Itcl_ListElem *pos, void *val); /* 18 */
    void (*itcl_SetListValue) (Itcl_ListElem *elemPtr, void *val); /* 19 */
    void (*itcl_EventuallyFree) (void *cdata, Tcl_FreeProc *fproc); /* 20 */
    void (*itcl_PreserveData) (void *cdata); /* 21 */
    void (*itcl_ReleaseData) (void *cdata); /* 22 */
    Itcl_InterpState (*itcl_SaveInterpState) (Tcl_Interp *interp, int status); /* 23 */
    int (*itcl_RestoreInterpState) (Tcl_Interp *interp, Itcl_InterpState state); /* 24 */
    void (*itcl_DiscardInterpState) (Itcl_InterpState state); /* 25 */
    void * (*itcl_Alloc) (size_t size); /* 26 */
    void (*itcl_Free) (void *ptr); /* 27 */
} ItclStubs;

extern const ItclStubs *itclStubsPtr;

#ifdef __cplusplus
}
#endif

#if defined(USE_ITCL_STUBS)

/*
 * Inline function declarations:
 */

/* Slot 0 is reserved */
/* Slot 1 is reserved */
#define Itcl_RegisterC \
	(itclStubsPtr->itcl_RegisterC) /* 2 */
#define Itcl_RegisterObjC \
	(itclStubsPtr->itcl_RegisterObjC) /* 3 */
#define Itcl_FindC \
	(itclStubsPtr->itcl_FindC) /* 4 */
#define Itcl_InitStack \
	(itclStubsPtr->itcl_InitStack) /* 5 */
#define Itcl_DeleteStack \
	(itclStubsPtr->itcl_DeleteStack) /* 6 */
#define Itcl_PushStack \
	(itclStubsPtr->itcl_PushStack) /* 7 */
#define Itcl_PopStack \
	(itclStubsPtr->itcl_PopStack) /* 8 */
#define Itcl_PeekStack \
	(itclStubsPtr->itcl_PeekStack) /* 9 */
#define Itcl_GetStackValue \
	(itclStubsPtr->itcl_GetStackValue) /* 10 */
#define Itcl_InitList \
	(itclStubsPtr->itcl_InitList) /* 11 */
#define Itcl_DeleteList \
	(itclStubsPtr->itcl_DeleteList) /* 12 */
#define Itcl_CreateListElem \
	(itclStubsPtr->itcl_CreateListElem) /* 13 */
#define Itcl_DeleteListElem \
	(itclStubsPtr->itcl_DeleteListElem) /* 14 */
#define Itcl_InsertList \
	(itclStubsPtr->itcl_InsertList) /* 15 */
#define Itcl_InsertListElem \
	(itclStubsPtr->itcl_InsertListElem) /* 16 */
#define Itcl_AppendList \
	(itclStubsPtr->itcl_AppendList) /* 17 */
#define Itcl_AppendListElem \
	(itclStubsPtr->itcl_AppendListElem) /* 18 */
#define Itcl_SetListValue \
	(itclStubsPtr->itcl_SetListValue) /* 19 */
#define Itcl_EventuallyFree \
	(itclStubsPtr->itcl_EventuallyFree) /* 20 */
#define Itcl_PreserveData \
	(itclStubsPtr->itcl_PreserveData) /* 21 */
#define Itcl_ReleaseData \
	(itclStubsPtr->itcl_ReleaseData) /* 22 */
#define Itcl_SaveInterpState \
	(itclStubsPtr->itcl_SaveInterpState) /* 23 */
#define Itcl_RestoreInterpState \
	(itclStubsPtr->itcl_RestoreInterpState) /* 24 */
#define Itcl_DiscardInterpState \
	(itclStubsPtr->itcl_DiscardInterpState) /* 25 */
#define Itcl_Alloc \
	(itclStubsPtr->itcl_Alloc) /* 26 */
#define Itcl_Free \
	(itclStubsPtr->itcl_Free) /* 27 */

#endif /* defined(USE_ITCL_STUBS) */

/* !END!: Do not edit above this line. */

#endif /* _ITCLDECLS */
