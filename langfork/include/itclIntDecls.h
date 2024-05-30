/*
 * This file is (mostly) automatically generated from itcl.decls.
 */

#ifndef _ITCLINTDECLS
#define _ITCLINTDECLS

/* !BEGIN!: Do not edit below this line. */

#define ITCLINT_STUBS_EPOCH 0
#define ITCLINT_STUBS_REVISION 152

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Exported function declarations:
 */

/* 0 */
ITCLAPI int		Itcl_IsClassNamespace(Tcl_Namespace *namesp);
/* 1 */
ITCLAPI int		Itcl_IsClass(Tcl_Command cmd);
/* 2 */
ITCLAPI ItclClass *	Itcl_FindClass(Tcl_Interp *interp, const char *path,
				int autoload);
/* 3 */
ITCLAPI int		Itcl_FindObject(Tcl_Interp *interp, const char *name,
				ItclObject **roPtr);
/* 4 */
ITCLAPI int		Itcl_IsObject(Tcl_Command cmd);
/* 5 */
ITCLAPI int		Itcl_ObjectIsa(ItclObject *contextObj,
				ItclClass *cdefn);
/* 6 */
ITCLAPI int		Itcl_Protection(Tcl_Interp *interp, int newLevel);
/* 7 */
ITCLAPI const char *	Itcl_ProtectionStr(int pLevel);
/* 8 */
ITCLAPI int		Itcl_CanAccess(ItclMemberFunc *memberPtr,
				Tcl_Namespace *fromNsPtr);
/* 9 */
ITCLAPI int		Itcl_CanAccessFunc(ItclMemberFunc *mfunc,
				Tcl_Namespace *fromNsPtr);
/* Slot 10 is reserved */
/* 11 */
ITCLAPI void		Itcl_ParseNamespPath(const char *name,
				Tcl_DString *buffer, const char **head,
				const char **tail);
/* 12 */
ITCLAPI int		Itcl_DecodeScopedCommand(Tcl_Interp *interp,
				const char *name, Tcl_Namespace **rNsPtr,
				char **rCmdPtr);
/* 13 */
ITCLAPI int		Itcl_EvalArgs(Tcl_Interp *interp, Tcl_Size objc,
				Tcl_Obj *const objv[]);
/* 14 */
ITCLAPI Tcl_Obj *	Itcl_CreateArgs(Tcl_Interp *interp,
				const char *string, Tcl_Size objc,
				Tcl_Obj *const objv[]);
/* Slot 15 is reserved */
/* Slot 16 is reserved */
/* 17 */
ITCLAPI int		Itcl_GetContext(Tcl_Interp *interp,
				ItclClass **iclsPtrPtr,
				ItclObject **ioPtrPtr);
/* 18 */
ITCLAPI void		Itcl_InitHierIter(ItclHierIter *iter,
				ItclClass *iclsPtr);
/* 19 */
ITCLAPI void		Itcl_DeleteHierIter(ItclHierIter *iter);
/* 20 */
ITCLAPI ItclClass *	Itcl_AdvanceHierIter(ItclHierIter *iter);
/* 21 */
ITCLAPI int		Itcl_FindClassesCmd(void *clientData,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* 22 */
ITCLAPI int		Itcl_FindObjectsCmd(void *clientData,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* Slot 23 is reserved */
/* 24 */
ITCLAPI int		Itcl_DelClassCmd(void *clientData,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* 25 */
ITCLAPI int		Itcl_DelObjectCmd(void *clientData,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* 26 */
ITCLAPI int		Itcl_ScopeCmd(void *clientData, Tcl_Interp *interp,
				int objc, Tcl_Obj *const objv[]);
/* 27 */
ITCLAPI int		Itcl_CodeCmd(void *clientData, Tcl_Interp *interp,
				int objc, Tcl_Obj *const objv[]);
/* 28 */
ITCLAPI int		Itcl_StubCreateCmd(void *clientData,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* 29 */
ITCLAPI int		Itcl_StubExistsCmd(void *clientData,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* 30 */
ITCLAPI int		Itcl_IsStub(Tcl_Command cmd);
/* 31 */
ITCLAPI int		Itcl_CreateClass(Tcl_Interp *interp,
				const char *path, ItclObjectInfo *info,
				ItclClass **rPtr);
/* 32 */
ITCLAPI int		Itcl_DeleteClass(Tcl_Interp *interp,
				ItclClass *iclsPtr);
/* 33 */
ITCLAPI Tcl_Namespace *	 Itcl_FindClassNamespace(Tcl_Interp *interp,
				const char *path);
/* 34 */
ITCLAPI int		Itcl_HandleClass(void *clientData,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* Slot 35 is reserved */
/* Slot 36 is reserved */
/* Slot 37 is reserved */
/* 38 */
ITCLAPI void		Itcl_BuildVirtualTables(ItclClass *iclsPtr);
/* 39 */
ITCLAPI int		Itcl_CreateVariable(Tcl_Interp *interp,
				ItclClass *iclsPtr, Tcl_Obj *name,
				char *init, char *config,
				ItclVariable **ivPtr);
/* 40 */
ITCLAPI void		Itcl_DeleteVariable(char *cdata);
/* 41 */
ITCLAPI const char *	Itcl_GetCommonVar(Tcl_Interp *interp,
				const char *name, ItclClass *contextClass);
/* Slot 42 is reserved */
/* Slot 43 is reserved */
/* 44 */
ITCLAPI int		Itcl_CreateObject(Tcl_Interp *interp,
				const char*name, ItclClass *iclsPtr,
				Tcl_Size objc, Tcl_Obj *const objv[],
				ItclObject **rioPtr);
/* 45 */
ITCLAPI int		Itcl_DeleteObject(Tcl_Interp *interp,
				ItclObject *contextObj);
/* 46 */
ITCLAPI int		Itcl_DestructObject(Tcl_Interp *interp,
				ItclObject *contextObj, int flags);
/* Slot 47 is reserved */
/* 48 */
ITCLAPI const char *	Itcl_GetInstanceVar(Tcl_Interp *interp,
				const char *name, ItclObject *contextIoPtr,
				ItclClass *contextIclsPtr);
/* Slot 49 is reserved */
/* 50 */
ITCLAPI int		Itcl_BodyCmd(void *dummy, Tcl_Interp *interp,
				int objc, Tcl_Obj *const objv[]);
/* 51 */
ITCLAPI int		Itcl_ConfigBodyCmd(void *dummy, Tcl_Interp *interp,
				int objc, Tcl_Obj *const objv[]);
/* 52 */
ITCLAPI int		Itcl_CreateMethod(Tcl_Interp *interp,
				ItclClass *iclsPtr, Tcl_Obj *namePtr,
				const char *arglist, const char *body);
/* 53 */
ITCLAPI int		Itcl_CreateProc(Tcl_Interp *interp,
				ItclClass *iclsPtr, Tcl_Obj *namePtr,
				const char *arglist, const char *body);
/* 54 */
ITCLAPI int		Itcl_CreateMemberFunc(Tcl_Interp *interp,
				ItclClass *iclsPtr, Tcl_Obj *name,
				const char *arglist, const char *body,
				ItclMemberFunc **mfuncPtr);
/* 55 */
ITCLAPI int		Itcl_ChangeMemberFunc(Tcl_Interp *interp,
				ItclMemberFunc *mfunc, const char *arglist,
				const char *body);
/* 56 */
ITCLAPI void		Itcl_DeleteMemberFunc(void *cdata);
/* 57 */
ITCLAPI int		Itcl_CreateMemberCode(Tcl_Interp *interp,
				ItclClass *iclsPtr, const char *arglist,
				const char *body, ItclMemberCode **mcodePtr);
/* 58 */
ITCLAPI void		Itcl_DeleteMemberCode(void *cdata);
/* 59 */
ITCLAPI int		Itcl_GetMemberCode(Tcl_Interp *interp,
				ItclMemberFunc *mfunc);
/* Slot 60 is reserved */
/* 61 */
ITCLAPI int		Itcl_EvalMemberCode(Tcl_Interp *interp,
				ItclMemberFunc *mfunc,
				ItclObject *contextObj, Tcl_Size objc,
				Tcl_Obj *const objv[]);
/* Slot 62 is reserved */
/* Slot 63 is reserved */
/* Slot 64 is reserved */
/* Slot 65 is reserved */
/* Slot 66 is reserved */
/* 67 */
ITCLAPI void		Itcl_GetMemberFuncUsage(ItclMemberFunc *mfunc,
				ItclObject *contextObj, Tcl_Obj *objPtr);
/* 68 */
ITCLAPI int		Itcl_ExecMethod(void *clientData, Tcl_Interp *interp,
				int objc, Tcl_Obj *const objv[]);
/* 69 */
ITCLAPI int		Itcl_ExecProc(void *clientData, Tcl_Interp *interp,
				int objc, Tcl_Obj *const objv[]);
/* Slot 70 is reserved */
/* 71 */
ITCLAPI int		Itcl_ConstructBase(Tcl_Interp *interp,
				ItclObject *contextObj,
				ItclClass *contextClass);
/* 72 */
ITCLAPI int		Itcl_InvokeMethodIfExists(Tcl_Interp *interp,
				const char *name, ItclClass *contextClass,
				ItclObject *contextObj, Tcl_Size objc,
				Tcl_Obj *const objv[]);
/* Slot 73 is reserved */
/* 74 */
ITCLAPI int		Itcl_ReportFuncErrors(Tcl_Interp *interp,
				ItclMemberFunc *mfunc,
				ItclObject *contextObj, int result);
/* 75 */
ITCLAPI int		Itcl_ParseInit(Tcl_Interp *interp,
				ItclObjectInfo *info);
/* 76 */
ITCLAPI int		Itcl_ClassCmd(void *clientData, Tcl_Interp *interp,
				int objc, Tcl_Obj *const objv[]);
/* 77 */
ITCLAPI int		Itcl_ClassInheritCmd(void *clientData,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* 78 */
ITCLAPI int		Itcl_ClassProtectionCmd(void *clientData,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* 79 */
ITCLAPI int		Itcl_ClassConstructorCmd(void *clientData,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* 80 */
ITCLAPI int		Itcl_ClassDestructorCmd(void *clientData,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* 81 */
ITCLAPI int		Itcl_ClassMethodCmd(void *clientData,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* 82 */
ITCLAPI int		Itcl_ClassProcCmd(void *clientData,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* 83 */
ITCLAPI int		Itcl_ClassVariableCmd(void *clientData,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* 84 */
ITCLAPI int		Itcl_ClassCommonCmd(void *clientData,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* 85 */
ITCLAPI int		Itcl_ParseVarResolver(Tcl_Interp *interp,
				const char *name, Tcl_Namespace *contextNs,
				int flags, Tcl_Var *rPtr);
/* 86 */
ITCLAPI int		Itcl_BiInit(Tcl_Interp *interp,
				ItclObjectInfo *infoPtr);
/* 87 */
ITCLAPI int		Itcl_InstallBiMethods(Tcl_Interp *interp,
				ItclClass *cdefn);
/* 88 */
ITCLAPI int		Itcl_BiIsaCmd(void *clientData, Tcl_Interp *interp,
				int objc, Tcl_Obj *const objv[]);
/* 89 */
ITCLAPI int		Itcl_BiConfigureCmd(void *clientData,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* 90 */
ITCLAPI int		Itcl_BiCgetCmd(void *clientData, Tcl_Interp *interp,
				int objc, Tcl_Obj *const objv[]);
/* 91 */
ITCLAPI int		Itcl_BiChainCmd(void *dummy, Tcl_Interp *interp,
				int objc, Tcl_Obj *const objv[]);
/* 92 */
ITCLAPI int		Itcl_BiInfoClassCmd(void *dummy, Tcl_Interp *interp,
				int objc, Tcl_Obj *const objv[]);
/* 93 */
ITCLAPI int		Itcl_BiInfoInheritCmd(void *dummy,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* 94 */
ITCLAPI int		Itcl_BiInfoHeritageCmd(void *dummy,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* 95 */
ITCLAPI int		Itcl_BiInfoFunctionCmd(void *dummy,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* 96 */
ITCLAPI int		Itcl_BiInfoVariableCmd(void *dummy,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* 97 */
ITCLAPI int		Itcl_BiInfoBodyCmd(void *dummy, Tcl_Interp *interp,
				int objc, Tcl_Obj *const objv[]);
/* 98 */
ITCLAPI int		Itcl_BiInfoArgsCmd(void *dummy, Tcl_Interp *interp,
				int objc, Tcl_Obj *const objv[]);
/* Slot 99 is reserved */
/* 100 */
ITCLAPI int		Itcl_EnsembleInit(Tcl_Interp *interp);
/* 101 */
ITCLAPI int		Itcl_CreateEnsemble(Tcl_Interp *interp,
				const char *ensName);
/* 102 */
ITCLAPI int		Itcl_AddEnsemblePart(Tcl_Interp *interp,
				const char *ensName, const char *partName,
				const char *usageInfo,
				Tcl_ObjCmdProc *objProc, void *clientData,
				Tcl_CmdDeleteProc *deleteProc);
/* 103 */
ITCLAPI int		Itcl_GetEnsemblePart(Tcl_Interp *interp,
				const char *ensName, const char *partName,
				Tcl_CmdInfo *infoPtr);
/* 104 */
ITCLAPI int		Itcl_IsEnsemble(Tcl_CmdInfo *infoPtr);
/* 105 */
ITCLAPI int		Itcl_GetEnsembleUsage(Tcl_Interp *interp,
				const char *ensName, Tcl_Obj *objPtr);
/* 106 */
ITCLAPI int		Itcl_GetEnsembleUsageForObj(Tcl_Interp *interp,
				Tcl_Obj *ensObjPtr, Tcl_Obj *objPtr);
/* 107 */
ITCLAPI int		Itcl_EnsembleCmd(void *clientData,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* 108 */
ITCLAPI int		Itcl_EnsPartCmd(void *clientData, Tcl_Interp *interp,
				int objc, Tcl_Obj *const objv[]);
/* 109 */
ITCLAPI int		Itcl_EnsembleErrorCmd(void *clientData,
				Tcl_Interp *interp, Tcl_Size objc,
				Tcl_Obj *const objv[]);
/* Slot 110 is reserved */
/* Slot 111 is reserved */
/* Slot 112 is reserved */
/* Slot 113 is reserved */
/* Slot 114 is reserved */
/* 115 */
ITCLAPI void		Itcl_Assert(const char *testExpr,
				const char *fileName, int lineNum);
/* 116 */
ITCLAPI int		Itcl_IsObjectCmd(void *clientData,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* 117 */
ITCLAPI int		Itcl_IsClassCmd(void *clientData, Tcl_Interp *interp,
				int objc, Tcl_Obj *const objv[]);
/* Slot 118 is reserved */
/* Slot 119 is reserved */
/* Slot 120 is reserved */
/* Slot 121 is reserved */
/* Slot 122 is reserved */
/* Slot 123 is reserved */
/* Slot 124 is reserved */
/* Slot 125 is reserved */
/* Slot 126 is reserved */
/* Slot 127 is reserved */
/* Slot 128 is reserved */
/* Slot 129 is reserved */
/* Slot 130 is reserved */
/* Slot 131 is reserved */
/* Slot 132 is reserved */
/* Slot 133 is reserved */
/* Slot 134 is reserved */
/* Slot 135 is reserved */
/* Slot 136 is reserved */
/* Slot 137 is reserved */
/* Slot 138 is reserved */
/* Slot 139 is reserved */
/* 140 */
ITCLAPI int		Itcl_FilterAddCmd(void *clientData,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* 141 */
ITCLAPI int		Itcl_FilterDeleteCmd(void *clientData,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* 142 */
ITCLAPI int		Itcl_ForwardAddCmd(void *clientData,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* 143 */
ITCLAPI int		Itcl_ForwardDeleteCmd(void *clientData,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* 144 */
ITCLAPI int		Itcl_MixinAddCmd(void *clientData,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* 145 */
ITCLAPI int		Itcl_MixinDeleteCmd(void *clientData,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* Slot 146 is reserved */
/* Slot 147 is reserved */
/* Slot 148 is reserved */
/* Slot 149 is reserved */
/* Slot 150 is reserved */
/* 151 */
ITCLAPI int		Itcl_BiInfoUnknownCmd(void *dummy,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* 152 */
ITCLAPI int		Itcl_BiInfoVarsCmd(void *dummy, Tcl_Interp *interp,
				int objc, Tcl_Obj *const objv[]);
/* 153 */
ITCLAPI int		Itcl_CanAccess2(ItclClass *iclsPtr, int protection,
				Tcl_Namespace *fromNsPtr);
/* Slot 154 is reserved */
/* Slot 155 is reserved */
/* Slot 156 is reserved */
/* Slot 157 is reserved */
/* Slot 158 is reserved */
/* Slot 159 is reserved */
/* 160 */
ITCLAPI int		Itcl_SetCallFrameResolver(Tcl_Interp *interp,
				Tcl_Resolve *resolvePtr);
/* 161 */
ITCLAPI int		ItclEnsembleSubCmd(void *clientData,
				Tcl_Interp *interp, const char *ensembleName,
				int objc, Tcl_Obj *const *objv,
				const char *functionName);
/* 162 */
ITCLAPI Tcl_Namespace *	 Itcl_GetUplevelNamespace(Tcl_Interp *interp,
				int level);
/* 163 */
ITCLAPI void *		Itcl_GetCallFrameClientData(Tcl_Interp *interp);
/* Slot 164 is reserved */
/* 165 */
ITCLAPI int		Itcl_SetCallFrameNamespace(Tcl_Interp *interp,
				Tcl_Namespace *nsPtr);
/* 166 */
ITCLAPI Tcl_Size	Itcl_GetCallFrameObjc(Tcl_Interp *interp);
/* 167 */
ITCLAPI Tcl_Obj *const * Itcl_GetCallFrameObjv(Tcl_Interp *interp);
/* 168 */
ITCLAPI int		Itcl_NWidgetCmd(void *infoPtr, Tcl_Interp *interp,
				int objc, Tcl_Obj *const objv[]);
/* 169 */
ITCLAPI int		Itcl_AddOptionCmd(void *infoPtr, Tcl_Interp *interp,
				int objc, Tcl_Obj *const objv[]);
/* 170 */
ITCLAPI int		Itcl_AddComponentCmd(void *infoPtr,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* 171 */
ITCLAPI int		Itcl_BiInfoOptionCmd(void *dummy, Tcl_Interp *interp,
				int objc, Tcl_Obj *const objv[]);
/* 172 */
ITCLAPI int		Itcl_BiInfoComponentCmd(void *dummy,
				Tcl_Interp *interp, int objc,
				Tcl_Obj *const objv[]);
/* 173 */
ITCLAPI int		Itcl_RenameCommand(Tcl_Interp *interp,
				const char *oldName, const char *newName);
/* 174 */
ITCLAPI int		Itcl_PushCallFrame(Tcl_Interp *interp,
				Tcl_CallFrame *framePtr,
				Tcl_Namespace *nsPtr, int isProcCallFrame);
/* 175 */
ITCLAPI void		Itcl_PopCallFrame(Tcl_Interp *interp);
/* 176 */
ITCLAPI Tcl_CallFrame *	 Itcl_GetUplevelCallFrame(Tcl_Interp *interp,
				int level);
/* 177 */
ITCLAPI Tcl_CallFrame *	 Itcl_ActivateCallFrame(Tcl_Interp *interp,
				Tcl_CallFrame *framePtr);
/* 178 */
ITCLAPI const char*	ItclSetInstanceVar(Tcl_Interp *interp,
				const char *name, const char *name2,
				const char *value, ItclObject *contextIoPtr,
				ItclClass *contextIclsPtr);
/* 179 */
ITCLAPI Tcl_Obj *	ItclCapitalize(const char *str);
/* 180 */
ITCLAPI int		ItclClassBaseCmd(void *clientData,
				Tcl_Interp *interp, int flags, int objc,
				Tcl_Obj *const objv[],
				ItclClass **iclsPtrPtr);
/* 181 */
ITCLAPI int		ItclCreateComponent(Tcl_Interp *interp,
				ItclClass *iclsPtr, Tcl_Obj *componentPtr,
				int type, ItclComponent **icPtrPtr);
/* 182 */
ITCLAPI void		Itcl_SetContext(Tcl_Interp *interp,
				ItclObject *ioPtr);
/* 183 */
ITCLAPI void		Itcl_UnsetContext(Tcl_Interp *interp);
/* 184 */
ITCLAPI const char *	ItclGetInstanceVar(Tcl_Interp *interp,
				const char *name, const char *name2,
				ItclObject *ioPtr, ItclClass *iclsPtr);

typedef struct ItclIntStubs {
    int magic;
    int epoch;
    int revision;
    void *hooks;

    int (*itcl_IsClassNamespace) (Tcl_Namespace *namesp); /* 0 */
    int (*itcl_IsClass) (Tcl_Command cmd); /* 1 */
    ItclClass * (*itcl_FindClass) (Tcl_Interp *interp, const char *path, int autoload); /* 2 */
    int (*itcl_FindObject) (Tcl_Interp *interp, const char *name, ItclObject **roPtr); /* 3 */
    int (*itcl_IsObject) (Tcl_Command cmd); /* 4 */
    int (*itcl_ObjectIsa) (ItclObject *contextObj, ItclClass *cdefn); /* 5 */
    int (*itcl_Protection) (Tcl_Interp *interp, int newLevel); /* 6 */
    const char * (*itcl_ProtectionStr) (int pLevel); /* 7 */
    int (*itcl_CanAccess) (ItclMemberFunc *memberPtr, Tcl_Namespace *fromNsPtr); /* 8 */
    int (*itcl_CanAccessFunc) (ItclMemberFunc *mfunc, Tcl_Namespace *fromNsPtr); /* 9 */
    void (*reserved10)(void);
    void (*itcl_ParseNamespPath) (const char *name, Tcl_DString *buffer, const char **head, const char **tail); /* 11 */
    int (*itcl_DecodeScopedCommand) (Tcl_Interp *interp, const char *name, Tcl_Namespace **rNsPtr, char **rCmdPtr); /* 12 */
    int (*itcl_EvalArgs) (Tcl_Interp *interp, Tcl_Size objc, Tcl_Obj *const objv[]); /* 13 */
    Tcl_Obj * (*itcl_CreateArgs) (Tcl_Interp *interp, const char *string, Tcl_Size objc, Tcl_Obj *const objv[]); /* 14 */
    void (*reserved15)(void);
    void (*reserved16)(void);
    int (*itcl_GetContext) (Tcl_Interp *interp, ItclClass **iclsPtrPtr, ItclObject **ioPtrPtr); /* 17 */
    void (*itcl_InitHierIter) (ItclHierIter *iter, ItclClass *iclsPtr); /* 18 */
    void (*itcl_DeleteHierIter) (ItclHierIter *iter); /* 19 */
    ItclClass * (*itcl_AdvanceHierIter) (ItclHierIter *iter); /* 20 */
    int (*itcl_FindClassesCmd) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 21 */
    int (*itcl_FindObjectsCmd) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 22 */
    void (*reserved23)(void);
    int (*itcl_DelClassCmd) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 24 */
    int (*itcl_DelObjectCmd) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 25 */
    int (*itcl_ScopeCmd) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 26 */
    int (*itcl_CodeCmd) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 27 */
    int (*itcl_StubCreateCmd) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 28 */
    int (*itcl_StubExistsCmd) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 29 */
    int (*itcl_IsStub) (Tcl_Command cmd); /* 30 */
    int (*itcl_CreateClass) (Tcl_Interp *interp, const char *path, ItclObjectInfo *info, ItclClass **rPtr); /* 31 */
    int (*itcl_DeleteClass) (Tcl_Interp *interp, ItclClass *iclsPtr); /* 32 */
    Tcl_Namespace * (*itcl_FindClassNamespace) (Tcl_Interp *interp, const char *path); /* 33 */
    int (*itcl_HandleClass) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 34 */
    void (*reserved35)(void);
    void (*reserved36)(void);
    void (*reserved37)(void);
    void (*itcl_BuildVirtualTables) (ItclClass *iclsPtr); /* 38 */
    int (*itcl_CreateVariable) (Tcl_Interp *interp, ItclClass *iclsPtr, Tcl_Obj *name, char *init, char *config, ItclVariable **ivPtr); /* 39 */
    void (*itcl_DeleteVariable) (char *cdata); /* 40 */
    const char * (*itcl_GetCommonVar) (Tcl_Interp *interp, const char *name, ItclClass *contextClass); /* 41 */
    void (*reserved42)(void);
    void (*reserved43)(void);
    int (*itcl_CreateObject) (Tcl_Interp *interp, const char*name, ItclClass *iclsPtr, Tcl_Size objc, Tcl_Obj *const objv[], ItclObject **rioPtr); /* 44 */
    int (*itcl_DeleteObject) (Tcl_Interp *interp, ItclObject *contextObj); /* 45 */
    int (*itcl_DestructObject) (Tcl_Interp *interp, ItclObject *contextObj, int flags); /* 46 */
    void (*reserved47)(void);
    const char * (*itcl_GetInstanceVar) (Tcl_Interp *interp, const char *name, ItclObject *contextIoPtr, ItclClass *contextIclsPtr); /* 48 */
    void (*reserved49)(void);
    int (*itcl_BodyCmd) (void *dummy, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 50 */
    int (*itcl_ConfigBodyCmd) (void *dummy, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 51 */
    int (*itcl_CreateMethod) (Tcl_Interp *interp, ItclClass *iclsPtr, Tcl_Obj *namePtr, const char *arglist, const char *body); /* 52 */
    int (*itcl_CreateProc) (Tcl_Interp *interp, ItclClass *iclsPtr, Tcl_Obj *namePtr, const char *arglist, const char *body); /* 53 */
    int (*itcl_CreateMemberFunc) (Tcl_Interp *interp, ItclClass *iclsPtr, Tcl_Obj *name, const char *arglist, const char *body, ItclMemberFunc **mfuncPtr); /* 54 */
    int (*itcl_ChangeMemberFunc) (Tcl_Interp *interp, ItclMemberFunc *mfunc, const char *arglist, const char *body); /* 55 */
    void (*itcl_DeleteMemberFunc) (void *cdata); /* 56 */
    int (*itcl_CreateMemberCode) (Tcl_Interp *interp, ItclClass *iclsPtr, const char *arglist, const char *body, ItclMemberCode **mcodePtr); /* 57 */
    void (*itcl_DeleteMemberCode) (void *cdata); /* 58 */
    int (*itcl_GetMemberCode) (Tcl_Interp *interp, ItclMemberFunc *mfunc); /* 59 */
    void (*reserved60)(void);
    int (*itcl_EvalMemberCode) (Tcl_Interp *interp, ItclMemberFunc *mfunc, ItclObject *contextObj, Tcl_Size objc, Tcl_Obj *const objv[]); /* 61 */
    void (*reserved62)(void);
    void (*reserved63)(void);
    void (*reserved64)(void);
    void (*reserved65)(void);
    void (*reserved66)(void);
    void (*itcl_GetMemberFuncUsage) (ItclMemberFunc *mfunc, ItclObject *contextObj, Tcl_Obj *objPtr); /* 67 */
    int (*itcl_ExecMethod) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 68 */
    int (*itcl_ExecProc) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 69 */
    void (*reserved70)(void);
    int (*itcl_ConstructBase) (Tcl_Interp *interp, ItclObject *contextObj, ItclClass *contextClass); /* 71 */
    int (*itcl_InvokeMethodIfExists) (Tcl_Interp *interp, const char *name, ItclClass *contextClass, ItclObject *contextObj, Tcl_Size objc, Tcl_Obj *const objv[]); /* 72 */
    void (*reserved73)(void);
    int (*itcl_ReportFuncErrors) (Tcl_Interp *interp, ItclMemberFunc *mfunc, ItclObject *contextObj, int result); /* 74 */
    int (*itcl_ParseInit) (Tcl_Interp *interp, ItclObjectInfo *info); /* 75 */
    int (*itcl_ClassCmd) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 76 */
    int (*itcl_ClassInheritCmd) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 77 */
    int (*itcl_ClassProtectionCmd) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 78 */
    int (*itcl_ClassConstructorCmd) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 79 */
    int (*itcl_ClassDestructorCmd) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 80 */
    int (*itcl_ClassMethodCmd) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 81 */
    int (*itcl_ClassProcCmd) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 82 */
    int (*itcl_ClassVariableCmd) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 83 */
    int (*itcl_ClassCommonCmd) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 84 */
    int (*itcl_ParseVarResolver) (Tcl_Interp *interp, const char *name, Tcl_Namespace *contextNs, int flags, Tcl_Var *rPtr); /* 85 */
    int (*itcl_BiInit) (Tcl_Interp *interp, ItclObjectInfo *infoPtr); /* 86 */
    int (*itcl_InstallBiMethods) (Tcl_Interp *interp, ItclClass *cdefn); /* 87 */
    int (*itcl_BiIsaCmd) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 88 */
    int (*itcl_BiConfigureCmd) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 89 */
    int (*itcl_BiCgetCmd) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 90 */
    int (*itcl_BiChainCmd) (void *dummy, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 91 */
    int (*itcl_BiInfoClassCmd) (void *dummy, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 92 */
    int (*itcl_BiInfoInheritCmd) (void *dummy, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 93 */
    int (*itcl_BiInfoHeritageCmd) (void *dummy, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 94 */
    int (*itcl_BiInfoFunctionCmd) (void *dummy, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 95 */
    int (*itcl_BiInfoVariableCmd) (void *dummy, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 96 */
    int (*itcl_BiInfoBodyCmd) (void *dummy, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 97 */
    int (*itcl_BiInfoArgsCmd) (void *dummy, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 98 */
    void (*reserved99)(void);
    int (*itcl_EnsembleInit) (Tcl_Interp *interp); /* 100 */
    int (*itcl_CreateEnsemble) (Tcl_Interp *interp, const char *ensName); /* 101 */
    int (*itcl_AddEnsemblePart) (Tcl_Interp *interp, const char *ensName, const char *partName, const char *usageInfo, Tcl_ObjCmdProc *objProc, void *clientData, Tcl_CmdDeleteProc *deleteProc); /* 102 */
    int (*itcl_GetEnsemblePart) (Tcl_Interp *interp, const char *ensName, const char *partName, Tcl_CmdInfo *infoPtr); /* 103 */
    int (*itcl_IsEnsemble) (Tcl_CmdInfo *infoPtr); /* 104 */
    int (*itcl_GetEnsembleUsage) (Tcl_Interp *interp, const char *ensName, Tcl_Obj *objPtr); /* 105 */
    int (*itcl_GetEnsembleUsageForObj) (Tcl_Interp *interp, Tcl_Obj *ensObjPtr, Tcl_Obj *objPtr); /* 106 */
    int (*itcl_EnsembleCmd) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 107 */
    int (*itcl_EnsPartCmd) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 108 */
    int (*itcl_EnsembleErrorCmd) (void *clientData, Tcl_Interp *interp, Tcl_Size objc, Tcl_Obj *const objv[]); /* 109 */
    void (*reserved110)(void);
    void (*reserved111)(void);
    void (*reserved112)(void);
    void (*reserved113)(void);
    void (*reserved114)(void);
    void (*itcl_Assert) (const char *testExpr, const char *fileName, int lineNum); /* 115 */
    int (*itcl_IsObjectCmd) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 116 */
    int (*itcl_IsClassCmd) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 117 */
    void (*reserved118)(void);
    void (*reserved119)(void);
    void (*reserved120)(void);
    void (*reserved121)(void);
    void (*reserved122)(void);
    void (*reserved123)(void);
    void (*reserved124)(void);
    void (*reserved125)(void);
    void (*reserved126)(void);
    void (*reserved127)(void);
    void (*reserved128)(void);
    void (*reserved129)(void);
    void (*reserved130)(void);
    void (*reserved131)(void);
    void (*reserved132)(void);
    void (*reserved133)(void);
    void (*reserved134)(void);
    void (*reserved135)(void);
    void (*reserved136)(void);
    void (*reserved137)(void);
    void (*reserved138)(void);
    void (*reserved139)(void);
    int (*itcl_FilterAddCmd) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 140 */
    int (*itcl_FilterDeleteCmd) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 141 */
    int (*itcl_ForwardAddCmd) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 142 */
    int (*itcl_ForwardDeleteCmd) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 143 */
    int (*itcl_MixinAddCmd) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 144 */
    int (*itcl_MixinDeleteCmd) (void *clientData, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 145 */
    void (*reserved146)(void);
    void (*reserved147)(void);
    void (*reserved148)(void);
    void (*reserved149)(void);
    void (*reserved150)(void);
    int (*itcl_BiInfoUnknownCmd) (void *dummy, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 151 */
    int (*itcl_BiInfoVarsCmd) (void *dummy, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 152 */
    int (*itcl_CanAccess2) (ItclClass *iclsPtr, int protection, Tcl_Namespace *fromNsPtr); /* 153 */
    void (*reserved154)(void);
    void (*reserved155)(void);
    void (*reserved156)(void);
    void (*reserved157)(void);
    void (*reserved158)(void);
    void (*reserved159)(void);
    int (*itcl_SetCallFrameResolver) (Tcl_Interp *interp, Tcl_Resolve *resolvePtr); /* 160 */
    int (*itclEnsembleSubCmd) (void *clientData, Tcl_Interp *interp, const char *ensembleName, int objc, Tcl_Obj *const *objv, const char *functionName); /* 161 */
    Tcl_Namespace * (*itcl_GetUplevelNamespace) (Tcl_Interp *interp, int level); /* 162 */
    void * (*itcl_GetCallFrameClientData) (Tcl_Interp *interp); /* 163 */
    void (*reserved164)(void);
    int (*itcl_SetCallFrameNamespace) (Tcl_Interp *interp, Tcl_Namespace *nsPtr); /* 165 */
    Tcl_Size (*itcl_GetCallFrameObjc) (Tcl_Interp *interp); /* 166 */
    Tcl_Obj *const * (*itcl_GetCallFrameObjv) (Tcl_Interp *interp); /* 167 */
    int (*itcl_NWidgetCmd) (void *infoPtr, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 168 */
    int (*itcl_AddOptionCmd) (void *infoPtr, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 169 */
    int (*itcl_AddComponentCmd) (void *infoPtr, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 170 */
    int (*itcl_BiInfoOptionCmd) (void *dummy, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 171 */
    int (*itcl_BiInfoComponentCmd) (void *dummy, Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]); /* 172 */
    int (*itcl_RenameCommand) (Tcl_Interp *interp, const char *oldName, const char *newName); /* 173 */
    int (*itcl_PushCallFrame) (Tcl_Interp *interp, Tcl_CallFrame *framePtr, Tcl_Namespace *nsPtr, int isProcCallFrame); /* 174 */
    void (*itcl_PopCallFrame) (Tcl_Interp *interp); /* 175 */
    Tcl_CallFrame * (*itcl_GetUplevelCallFrame) (Tcl_Interp *interp, int level); /* 176 */
    Tcl_CallFrame * (*itcl_ActivateCallFrame) (Tcl_Interp *interp, Tcl_CallFrame *framePtr); /* 177 */
    const char* (*itclSetInstanceVar) (Tcl_Interp *interp, const char *name, const char *name2, const char *value, ItclObject *contextIoPtr, ItclClass *contextIclsPtr); /* 178 */
    Tcl_Obj * (*itclCapitalize) (const char *str); /* 179 */
    int (*itclClassBaseCmd) (void *clientData, Tcl_Interp *interp, int flags, int objc, Tcl_Obj *const objv[], ItclClass **iclsPtrPtr); /* 180 */
    int (*itclCreateComponent) (Tcl_Interp *interp, ItclClass *iclsPtr, Tcl_Obj *componentPtr, int type, ItclComponent **icPtrPtr); /* 181 */
    void (*itcl_SetContext) (Tcl_Interp *interp, ItclObject *ioPtr); /* 182 */
    void (*itcl_UnsetContext) (Tcl_Interp *interp); /* 183 */
    const char * (*itclGetInstanceVar) (Tcl_Interp *interp, const char *name, const char *name2, ItclObject *ioPtr, ItclClass *iclsPtr); /* 184 */
} ItclIntStubs;

extern const ItclIntStubs *itclIntStubsPtr;

#ifdef __cplusplus
}
#endif

#if defined(USE_ITCL_STUBS)

/*
 * Inline function declarations:
 */

#define Itcl_IsClassNamespace \
	(itclIntStubsPtr->itcl_IsClassNamespace) /* 0 */
#define Itcl_IsClass \
	(itclIntStubsPtr->itcl_IsClass) /* 1 */
#define Itcl_FindClass \
	(itclIntStubsPtr->itcl_FindClass) /* 2 */
#define Itcl_FindObject \
	(itclIntStubsPtr->itcl_FindObject) /* 3 */
#define Itcl_IsObject \
	(itclIntStubsPtr->itcl_IsObject) /* 4 */
#define Itcl_ObjectIsa \
	(itclIntStubsPtr->itcl_ObjectIsa) /* 5 */
#define Itcl_Protection \
	(itclIntStubsPtr->itcl_Protection) /* 6 */
#define Itcl_ProtectionStr \
	(itclIntStubsPtr->itcl_ProtectionStr) /* 7 */
#define Itcl_CanAccess \
	(itclIntStubsPtr->itcl_CanAccess) /* 8 */
#define Itcl_CanAccessFunc \
	(itclIntStubsPtr->itcl_CanAccessFunc) /* 9 */
/* Slot 10 is reserved */
#define Itcl_ParseNamespPath \
	(itclIntStubsPtr->itcl_ParseNamespPath) /* 11 */
#define Itcl_DecodeScopedCommand \
	(itclIntStubsPtr->itcl_DecodeScopedCommand) /* 12 */
#define Itcl_EvalArgs \
	(itclIntStubsPtr->itcl_EvalArgs) /* 13 */
#define Itcl_CreateArgs \
	(itclIntStubsPtr->itcl_CreateArgs) /* 14 */
/* Slot 15 is reserved */
/* Slot 16 is reserved */
#define Itcl_GetContext \
	(itclIntStubsPtr->itcl_GetContext) /* 17 */
#define Itcl_InitHierIter \
	(itclIntStubsPtr->itcl_InitHierIter) /* 18 */
#define Itcl_DeleteHierIter \
	(itclIntStubsPtr->itcl_DeleteHierIter) /* 19 */
#define Itcl_AdvanceHierIter \
	(itclIntStubsPtr->itcl_AdvanceHierIter) /* 20 */
#define Itcl_FindClassesCmd \
	(itclIntStubsPtr->itcl_FindClassesCmd) /* 21 */
#define Itcl_FindObjectsCmd \
	(itclIntStubsPtr->itcl_FindObjectsCmd) /* 22 */
/* Slot 23 is reserved */
#define Itcl_DelClassCmd \
	(itclIntStubsPtr->itcl_DelClassCmd) /* 24 */
#define Itcl_DelObjectCmd \
	(itclIntStubsPtr->itcl_DelObjectCmd) /* 25 */
#define Itcl_ScopeCmd \
	(itclIntStubsPtr->itcl_ScopeCmd) /* 26 */
#define Itcl_CodeCmd \
	(itclIntStubsPtr->itcl_CodeCmd) /* 27 */
#define Itcl_StubCreateCmd \
	(itclIntStubsPtr->itcl_StubCreateCmd) /* 28 */
#define Itcl_StubExistsCmd \
	(itclIntStubsPtr->itcl_StubExistsCmd) /* 29 */
#define Itcl_IsStub \
	(itclIntStubsPtr->itcl_IsStub) /* 30 */
#define Itcl_CreateClass \
	(itclIntStubsPtr->itcl_CreateClass) /* 31 */
#define Itcl_DeleteClass \
	(itclIntStubsPtr->itcl_DeleteClass) /* 32 */
#define Itcl_FindClassNamespace \
	(itclIntStubsPtr->itcl_FindClassNamespace) /* 33 */
#define Itcl_HandleClass \
	(itclIntStubsPtr->itcl_HandleClass) /* 34 */
/* Slot 35 is reserved */
/* Slot 36 is reserved */
/* Slot 37 is reserved */
#define Itcl_BuildVirtualTables \
	(itclIntStubsPtr->itcl_BuildVirtualTables) /* 38 */
#define Itcl_CreateVariable \
	(itclIntStubsPtr->itcl_CreateVariable) /* 39 */
#define Itcl_DeleteVariable \
	(itclIntStubsPtr->itcl_DeleteVariable) /* 40 */
#define Itcl_GetCommonVar \
	(itclIntStubsPtr->itcl_GetCommonVar) /* 41 */
/* Slot 42 is reserved */
/* Slot 43 is reserved */
#define Itcl_CreateObject \
	(itclIntStubsPtr->itcl_CreateObject) /* 44 */
#define Itcl_DeleteObject \
	(itclIntStubsPtr->itcl_DeleteObject) /* 45 */
#define Itcl_DestructObject \
	(itclIntStubsPtr->itcl_DestructObject) /* 46 */
/* Slot 47 is reserved */
#define Itcl_GetInstanceVar \
	(itclIntStubsPtr->itcl_GetInstanceVar) /* 48 */
/* Slot 49 is reserved */
#define Itcl_BodyCmd \
	(itclIntStubsPtr->itcl_BodyCmd) /* 50 */
#define Itcl_ConfigBodyCmd \
	(itclIntStubsPtr->itcl_ConfigBodyCmd) /* 51 */
#define Itcl_CreateMethod \
	(itclIntStubsPtr->itcl_CreateMethod) /* 52 */
#define Itcl_CreateProc \
	(itclIntStubsPtr->itcl_CreateProc) /* 53 */
#define Itcl_CreateMemberFunc \
	(itclIntStubsPtr->itcl_CreateMemberFunc) /* 54 */
#define Itcl_ChangeMemberFunc \
	(itclIntStubsPtr->itcl_ChangeMemberFunc) /* 55 */
#define Itcl_DeleteMemberFunc \
	(itclIntStubsPtr->itcl_DeleteMemberFunc) /* 56 */
#define Itcl_CreateMemberCode \
	(itclIntStubsPtr->itcl_CreateMemberCode) /* 57 */
#define Itcl_DeleteMemberCode \
	(itclIntStubsPtr->itcl_DeleteMemberCode) /* 58 */
#define Itcl_GetMemberCode \
	(itclIntStubsPtr->itcl_GetMemberCode) /* 59 */
/* Slot 60 is reserved */
#define Itcl_EvalMemberCode \
	(itclIntStubsPtr->itcl_EvalMemberCode) /* 61 */
/* Slot 62 is reserved */
/* Slot 63 is reserved */
/* Slot 64 is reserved */
/* Slot 65 is reserved */
/* Slot 66 is reserved */
#define Itcl_GetMemberFuncUsage \
	(itclIntStubsPtr->itcl_GetMemberFuncUsage) /* 67 */
#define Itcl_ExecMethod \
	(itclIntStubsPtr->itcl_ExecMethod) /* 68 */
#define Itcl_ExecProc \
	(itclIntStubsPtr->itcl_ExecProc) /* 69 */
/* Slot 70 is reserved */
#define Itcl_ConstructBase \
	(itclIntStubsPtr->itcl_ConstructBase) /* 71 */
#define Itcl_InvokeMethodIfExists \
	(itclIntStubsPtr->itcl_InvokeMethodIfExists) /* 72 */
/* Slot 73 is reserved */
#define Itcl_ReportFuncErrors \
	(itclIntStubsPtr->itcl_ReportFuncErrors) /* 74 */
#define Itcl_ParseInit \
	(itclIntStubsPtr->itcl_ParseInit) /* 75 */
#define Itcl_ClassCmd \
	(itclIntStubsPtr->itcl_ClassCmd) /* 76 */
#define Itcl_ClassInheritCmd \
	(itclIntStubsPtr->itcl_ClassInheritCmd) /* 77 */
#define Itcl_ClassProtectionCmd \
	(itclIntStubsPtr->itcl_ClassProtectionCmd) /* 78 */
#define Itcl_ClassConstructorCmd \
	(itclIntStubsPtr->itcl_ClassConstructorCmd) /* 79 */
#define Itcl_ClassDestructorCmd \
	(itclIntStubsPtr->itcl_ClassDestructorCmd) /* 80 */
#define Itcl_ClassMethodCmd \
	(itclIntStubsPtr->itcl_ClassMethodCmd) /* 81 */
#define Itcl_ClassProcCmd \
	(itclIntStubsPtr->itcl_ClassProcCmd) /* 82 */
#define Itcl_ClassVariableCmd \
	(itclIntStubsPtr->itcl_ClassVariableCmd) /* 83 */
#define Itcl_ClassCommonCmd \
	(itclIntStubsPtr->itcl_ClassCommonCmd) /* 84 */
#define Itcl_ParseVarResolver \
	(itclIntStubsPtr->itcl_ParseVarResolver) /* 85 */
#define Itcl_BiInit \
	(itclIntStubsPtr->itcl_BiInit) /* 86 */
#define Itcl_InstallBiMethods \
	(itclIntStubsPtr->itcl_InstallBiMethods) /* 87 */
#define Itcl_BiIsaCmd \
	(itclIntStubsPtr->itcl_BiIsaCmd) /* 88 */
#define Itcl_BiConfigureCmd \
	(itclIntStubsPtr->itcl_BiConfigureCmd) /* 89 */
#define Itcl_BiCgetCmd \
	(itclIntStubsPtr->itcl_BiCgetCmd) /* 90 */
#define Itcl_BiChainCmd \
	(itclIntStubsPtr->itcl_BiChainCmd) /* 91 */
#define Itcl_BiInfoClassCmd \
	(itclIntStubsPtr->itcl_BiInfoClassCmd) /* 92 */
#define Itcl_BiInfoInheritCmd \
	(itclIntStubsPtr->itcl_BiInfoInheritCmd) /* 93 */
#define Itcl_BiInfoHeritageCmd \
	(itclIntStubsPtr->itcl_BiInfoHeritageCmd) /* 94 */
#define Itcl_BiInfoFunctionCmd \
	(itclIntStubsPtr->itcl_BiInfoFunctionCmd) /* 95 */
#define Itcl_BiInfoVariableCmd \
	(itclIntStubsPtr->itcl_BiInfoVariableCmd) /* 96 */
#define Itcl_BiInfoBodyCmd \
	(itclIntStubsPtr->itcl_BiInfoBodyCmd) /* 97 */
#define Itcl_BiInfoArgsCmd \
	(itclIntStubsPtr->itcl_BiInfoArgsCmd) /* 98 */
/* Slot 99 is reserved */
#define Itcl_EnsembleInit \
	(itclIntStubsPtr->itcl_EnsembleInit) /* 100 */
#define Itcl_CreateEnsemble \
	(itclIntStubsPtr->itcl_CreateEnsemble) /* 101 */
#define Itcl_AddEnsemblePart \
	(itclIntStubsPtr->itcl_AddEnsemblePart) /* 102 */
#define Itcl_GetEnsemblePart \
	(itclIntStubsPtr->itcl_GetEnsemblePart) /* 103 */
#define Itcl_IsEnsemble \
	(itclIntStubsPtr->itcl_IsEnsemble) /* 104 */
#define Itcl_GetEnsembleUsage \
	(itclIntStubsPtr->itcl_GetEnsembleUsage) /* 105 */
#define Itcl_GetEnsembleUsageForObj \
	(itclIntStubsPtr->itcl_GetEnsembleUsageForObj) /* 106 */
#define Itcl_EnsembleCmd \
	(itclIntStubsPtr->itcl_EnsembleCmd) /* 107 */
#define Itcl_EnsPartCmd \
	(itclIntStubsPtr->itcl_EnsPartCmd) /* 108 */
#define Itcl_EnsembleErrorCmd \
	(itclIntStubsPtr->itcl_EnsembleErrorCmd) /* 109 */
/* Slot 110 is reserved */
/* Slot 111 is reserved */
/* Slot 112 is reserved */
/* Slot 113 is reserved */
/* Slot 114 is reserved */
#define Itcl_Assert \
	(itclIntStubsPtr->itcl_Assert) /* 115 */
#define Itcl_IsObjectCmd \
	(itclIntStubsPtr->itcl_IsObjectCmd) /* 116 */
#define Itcl_IsClassCmd \
	(itclIntStubsPtr->itcl_IsClassCmd) /* 117 */
/* Slot 118 is reserved */
/* Slot 119 is reserved */
/* Slot 120 is reserved */
/* Slot 121 is reserved */
/* Slot 122 is reserved */
/* Slot 123 is reserved */
/* Slot 124 is reserved */
/* Slot 125 is reserved */
/* Slot 126 is reserved */
/* Slot 127 is reserved */
/* Slot 128 is reserved */
/* Slot 129 is reserved */
/* Slot 130 is reserved */
/* Slot 131 is reserved */
/* Slot 132 is reserved */
/* Slot 133 is reserved */
/* Slot 134 is reserved */
/* Slot 135 is reserved */
/* Slot 136 is reserved */
/* Slot 137 is reserved */
/* Slot 138 is reserved */
/* Slot 139 is reserved */
#define Itcl_FilterAddCmd \
	(itclIntStubsPtr->itcl_FilterAddCmd) /* 140 */
#define Itcl_FilterDeleteCmd \
	(itclIntStubsPtr->itcl_FilterDeleteCmd) /* 141 */
#define Itcl_ForwardAddCmd \
	(itclIntStubsPtr->itcl_ForwardAddCmd) /* 142 */
#define Itcl_ForwardDeleteCmd \
	(itclIntStubsPtr->itcl_ForwardDeleteCmd) /* 143 */
#define Itcl_MixinAddCmd \
	(itclIntStubsPtr->itcl_MixinAddCmd) /* 144 */
#define Itcl_MixinDeleteCmd \
	(itclIntStubsPtr->itcl_MixinDeleteCmd) /* 145 */
/* Slot 146 is reserved */
/* Slot 147 is reserved */
/* Slot 148 is reserved */
/* Slot 149 is reserved */
/* Slot 150 is reserved */
#define Itcl_BiInfoUnknownCmd \
	(itclIntStubsPtr->itcl_BiInfoUnknownCmd) /* 151 */
#define Itcl_BiInfoVarsCmd \
	(itclIntStubsPtr->itcl_BiInfoVarsCmd) /* 152 */
#define Itcl_CanAccess2 \
	(itclIntStubsPtr->itcl_CanAccess2) /* 153 */
/* Slot 154 is reserved */
/* Slot 155 is reserved */
/* Slot 156 is reserved */
/* Slot 157 is reserved */
/* Slot 158 is reserved */
/* Slot 159 is reserved */
#define Itcl_SetCallFrameResolver \
	(itclIntStubsPtr->itcl_SetCallFrameResolver) /* 160 */
#define ItclEnsembleSubCmd \
	(itclIntStubsPtr->itclEnsembleSubCmd) /* 161 */
#define Itcl_GetUplevelNamespace \
	(itclIntStubsPtr->itcl_GetUplevelNamespace) /* 162 */
#define Itcl_GetCallFrameClientData \
	(itclIntStubsPtr->itcl_GetCallFrameClientData) /* 163 */
/* Slot 164 is reserved */
#define Itcl_SetCallFrameNamespace \
	(itclIntStubsPtr->itcl_SetCallFrameNamespace) /* 165 */
#define Itcl_GetCallFrameObjc \
	(itclIntStubsPtr->itcl_GetCallFrameObjc) /* 166 */
#define Itcl_GetCallFrameObjv \
	(itclIntStubsPtr->itcl_GetCallFrameObjv) /* 167 */
#define Itcl_NWidgetCmd \
	(itclIntStubsPtr->itcl_NWidgetCmd) /* 168 */
#define Itcl_AddOptionCmd \
	(itclIntStubsPtr->itcl_AddOptionCmd) /* 169 */
#define Itcl_AddComponentCmd \
	(itclIntStubsPtr->itcl_AddComponentCmd) /* 170 */
#define Itcl_BiInfoOptionCmd \
	(itclIntStubsPtr->itcl_BiInfoOptionCmd) /* 171 */
#define Itcl_BiInfoComponentCmd \
	(itclIntStubsPtr->itcl_BiInfoComponentCmd) /* 172 */
#define Itcl_RenameCommand \
	(itclIntStubsPtr->itcl_RenameCommand) /* 173 */
#define Itcl_PushCallFrame \
	(itclIntStubsPtr->itcl_PushCallFrame) /* 174 */
#define Itcl_PopCallFrame \
	(itclIntStubsPtr->itcl_PopCallFrame) /* 175 */
#define Itcl_GetUplevelCallFrame \
	(itclIntStubsPtr->itcl_GetUplevelCallFrame) /* 176 */
#define Itcl_ActivateCallFrame \
	(itclIntStubsPtr->itcl_ActivateCallFrame) /* 177 */
#define ItclSetInstanceVar \
	(itclIntStubsPtr->itclSetInstanceVar) /* 178 */
#define ItclCapitalize \
	(itclIntStubsPtr->itclCapitalize) /* 179 */
#define ItclClassBaseCmd \
	(itclIntStubsPtr->itclClassBaseCmd) /* 180 */
#define ItclCreateComponent \
	(itclIntStubsPtr->itclCreateComponent) /* 181 */
#define Itcl_SetContext \
	(itclIntStubsPtr->itcl_SetContext) /* 182 */
#define Itcl_UnsetContext \
	(itclIntStubsPtr->itcl_UnsetContext) /* 183 */
#define ItclGetInstanceVar \
	(itclIntStubsPtr->itclGetInstanceVar) /* 184 */

#endif /* defined(USE_ITCL_STUBS) */

/* !END!: Do not edit above this line. */

#endif /* _ITCLINTDECLS */
