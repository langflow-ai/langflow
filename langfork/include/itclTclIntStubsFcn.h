/* these functions are Tcl internal stubs so make an Itcl_* wrapper */
MODULE_SCOPE void Itcl_GetVariableFullName (Tcl_Interp * interp,
                Tcl_Var variable, Tcl_Obj * objPtr);
MODULE_SCOPE Tcl_Var Itcl_FindNamespaceVar (Tcl_Interp * interp,
                 const char * name, Tcl_Namespace * contextNsPtr, int flags);
MODULE_SCOPE void Itcl_SetNamespaceResolvers (Tcl_Namespace * namespacePtr,
        Tcl_ResolveCmdProc * cmdProc, Tcl_ResolveVarProc * varProc,
        Tcl_ResolveCompiledVarProc * compiledVarProc);

#ifndef _TCL_PROC_DEFINED
typedef struct Tcl_Proc_ *Tcl_Proc;
#define _TCL_PROC_DEFINED 1
#endif
#ifndef _TCL_RESOLVE_DEFINED
struct Tcl_Resolve;
#endif

#define Tcl_GetOriginalCommand _Tcl_GetOriginalCommand
#define Tcl_CreateProc _Tcl_CreateProc
#define Tcl_ProcDeleteProc _Tcl_ProcDeleteProc
#define Tcl_GetObjInterpProc _Tcl_GetObjInterpProc

MODULE_SCOPE Tcl_Command _Tcl_GetOriginalCommand(Tcl_Command command);
MODULE_SCOPE int _Tcl_CreateProc(Tcl_Interp *interp, Tcl_Namespace *nsPtr,
	 const char *procName, Tcl_Obj *argsPtr, Tcl_Obj *bodyPtr,
        Tcl_Proc *procPtrPtr);
MODULE_SCOPE void _Tcl_ProcDeleteProc(void *clientData);
MODULE_SCOPE Tcl_ObjCmdProc *_Tcl_GetObjInterpProc(void);
MODULE_SCOPE int Tcl_RenameCommand(Tcl_Interp *interp, const char *oldName,
	const char *newName);
MODULE_SCOPE Tcl_HashTable *Itcl_GetNamespaceChildTable(Tcl_Namespace *nsPtr);
MODULE_SCOPE Tcl_HashTable *Itcl_GetNamespaceCommandTable(Tcl_Namespace *nsPtr);
MODULE_SCOPE int Itcl_InitRewriteEnsemble(Tcl_Interp *interp, size_t numRemoved,
	size_t numInserted, size_t objc, Tcl_Obj *const *objv);
MODULE_SCOPE void Itcl_ResetRewriteEnsemble(Tcl_Interp *interp,
        int isRootEnsemble);


