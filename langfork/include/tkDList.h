/*
 * tkDList.h --
 *
 * A list is headed by pointers to first and last element. The elements
 * are doubly linked so that an arbitrary element can be removed without
 * a need to traverse the list. New elements can be added to the list
 * before or after an existing element or at the head/tail of the list.
 * A list may be traversed in the forward or backward direction.
 *
 * Copyright (c) 2018 Gregor Cramer.
 *
 * See the file "license.terms" for information on usage and redistribution of
 * this file, and for a DISCLAIMER OF ALL WARRANTIES.
 */

/*
 * Note that this file will not be included in header files, it is the purpose
 * of this file to be included in source files only. Thus we are not using the
 * prefix "Tk_" here for functions, because all the functions have private scope.
 */

/*
 * -------------------------------------------------------------------------------
 * Use the double linked list in the following way:
 * -------------------------------------------------------------------------------
 * typedef struct MyListEntry { TK_DLIST_LINKS(MyListEntry); int value; } MyListEntry;
 * TK_DLIST_DEFINE(MyList, MyListEntry);
 * MyList listHdr = TK_DLIST_LIST_INITIALIZER; // or MyList_Init(&listHdr)
 * MyListEntry *p;
 * int i = 0;
 * MyList_Append(&listHdr, (MyListEntry *)ckalloc(sizeof(MyListEntry)));
 * MyList_Append(&listHdr, (MyListEntry *)ckalloc(sizeof(MyListEntry)));
 * TK_DLIST_FOREACH(p, &listHdr) { p->value = i++; }
 * // ...
 * MyList_RemoveHead(&listHdr);
 * MyList_RemoveHead(&listHdr);
 * MyList_Clear(MyListEntry, &listHdr); // invokes ckfree() for each element
 * -------------------------------------------------------------------------------
 * IMPORTANT NOTE: TK_DLIST_LINKS must be used at start of struct!
 */

#ifndef TK_DLIST_DEFINED
#define TK_DLIST_DEFINED

#include "tkInt.h"

/*
 * List definitions.
 */

#define TK_DLIST_LINKS(ElemType)						\
struct {									\
    struct ElemType *prev;	/* previous element */				\
    struct ElemType *next;	/* next element */				\
} _dl_

#define TK_DLIST_LIST_INITIALIZER { NULL, NULL }
#define TK_DLIST_ELEM_INITIALIZER { NULL, NULL }

/*************************************************************************/
/*
 * DList_Init: Initialize list header. This can also be used to clear the
 * list.
 *
 * See also: DList_Clear()
 */
/*************************************************************************/
/*
 * DList_ElemInit: Initialize a list element.
 */
/*************************************************************************/
/*
 * DList_InsertAfter: Insert 'elem' after 'listElem'. 'elem' must not
 * be linked, but 'listElem' must be linked.
 */
/*************************************************************************/
/*
 * DList_InsertBefore: Insert 'elem' before 'listElem'. 'elem' must not
 * be linked, but 'listElem' must be linked.
 */
/*************************************************************************/
/*
 * DList_Prepend: Insert 'elem' at start of list. This element must not
 * be linked.
 *
 * See also: DList_Append()
 */
/*************************************************************************/
/*
 * DList_Append: Append 'elem' to end of list. This element must not
 * be linked.
 *
 * See also: DList_Prepend()
 */
/*************************************************************************/
/*
 * DList_Move: Append all list items of 'src' to end of 'dst'.
 */
/*************************************************************************/
/*
 * DList_Remove: Remove 'elem' from list. This element must be linked.
 *
 * See also: DList_Free()
 */
/*************************************************************************/
/*
 * DList_Free: Remove 'elem' from list and free it. This element must
 * be linked.
 *
 * See also: DList_Remove()
 */
/*************************************************************************/
/*
 * DList_RemoveHead: Remove first element from list. The list must
 * not be empty.
 *
 * See also: DList_FreeHead()
 */
/*************************************************************************/
/*
 * DList_RemoveTail: Remove last element from list. The list must
 * not be empty.
 *
 * See also: DList_FreeTail()
 */
/*************************************************************************/
/*
 * DList_FreeHead: Remove first element from list and free it.
 * The list must not be empty.
 *
 * See also: DList_RemoveHead()
 */
/*************************************************************************/
/*
 * DList_FreeTail: Remove last element from list and free it.
 * The list must not be empty.
 *
 * See also: DList_RemoveTail()
 */
/*************************************************************************/
/*
 * DList_SwapElems: Swap positions of given elements 'lhs' and 'rhs'.
 * Both elements must be linked, and must belong to same list.
 */
/*************************************************************************/
/*
 * DList_Clear: Clear whole list and free all elements.
 *
 * See also: DList_Init
 */
/*************************************************************************/
/*
 * DList_Traverse: Iterate over all elements in list from first to last.
 * Call given function func(head, elem) for each element. The function has
 * to return the next element in list to traverse, normally this is
 * DList_Next(elem).
 *
 * See also: TK_DLIST_FOREACH, TK_DLIST_FOREACH_REVERSE
 */
/*************************************************************************/
/*
 * DList_First: Return pointer of first element in list, maybe it's NULL.
 */
/*************************************************************************/
/*
 * DList_Last: Return pointer of last element in list, maybe it's NULL.
 */
/*************************************************************************/
/*
 * DList_Next: Return pointer of next element after 'elem', maybe it's NULL.
 *
 * See also: DList_Prev()
 */
/*************************************************************************/
/*
 * DList_Prev: Return pointer of previous element before 'elem', maybe it's
 * NULL.
 *
 * See also: DList_Next()
 */
/*************************************************************************/
/*
 * DList_IsEmpty: Test whether given list is empty.
 */
/*************************************************************************/
/*
 * DList_IsLinked: Test whether given element is linked.
 */
/*************************************************************************/
/*
 * DList_IsFirst: Test whether given element is first element in list.
 * Note that 'elem' must be linked.
 *
 * See also: DList_IsLast(), DList_IsLinked()
 */
/*************************************************************************/
/*
 * DList_IsLast: Test whether given element is last element in list.
 * Note that 'elem' must be linked.
 *
 * See also: DList_IsFirst(), DList_IsLinked()
 */
/*************************************************************************/
/*
 * DList_Size: Count number of elements in given list.
 */
/*************************************************************************/
/*
 * TK_DLIST_FOREACH: Iterate over all elements in list from first to last.
 * 'var' is the name of the variable which points to current element.
 *
 * See also: TK_DLIST_FOREACH_REVERSE, DList_Traverse()
 */
/*************************************************************************/
/*
 * TK_DLIST_FOREACH_REVERSE: Iterate over all elements in list from last
 * to first (backwards). 'var' is the name of the variable which points to
 * current element.
 */
/*************************************************************************/

#if defined(__GNUC__) || defined(__clang__)
# define __TK_DLIST_UNUSED __attribute__((unused))
#else
# define __TK_DLIST_UNUSED
#endif

#define TK_DLIST_DEFINE(LT, ElemType) /* LT = type of head/list */		\
/* ------------------------------------------------------------------------- */	\
typedef struct LT {								\
    struct ElemType *first;	/* first element */				\
    struct ElemType *last;	/* last element */				\
} LT;										\
										\
typedef struct ElemType *(LT##_Func)(LT *head, struct ElemType *elem);		\
										\
__TK_DLIST_UNUSED								\
static void									\
LT##_Init(LT *head)								\
{										\
    assert(head);								\
    head->first = NULL;								\
    head->last = NULL;								\
}										\
										\
__TK_DLIST_UNUSED								\
static void									\
LT##_ElemInit(struct ElemType *elem)						\
{										\
    assert(elem);								\
    elem->_dl_.next = NULL;							\
    elem->_dl_.prev = NULL;							\
}										\
										\
__TK_DLIST_UNUSED								\
static int									\
LT##_IsEmpty(LT *head)								\
{										\
    assert(head);								\
    return head->first == NULL;							\
}										\
										\
__TK_DLIST_UNUSED								\
static int									\
LT##_IsLinked(struct ElemType *elem)						\
{										\
    assert(elem);								\
    return elem->_dl_.next && elem->_dl_.prev;					\
}										\
										\
__TK_DLIST_UNUSED								\
static int									\
LT##_IsFirst(struct ElemType *elem)						\
{										\
    assert(LT##_IsLinked(elem));						\
    return elem->_dl_.prev->_dl_.prev == elem;					\
}										\
										\
__TK_DLIST_UNUSED								\
static int									\
LT##_IsLast(struct ElemType *elem)						\
{										\
    assert(LT##_IsLinked(elem));						\
    return elem->_dl_.next->_dl_.next == elem;					\
}										\
										\
__TK_DLIST_UNUSED								\
static struct ElemType *							\
LT##_First(LT *head)								\
{										\
    assert(head);								\
    return head->first;								\
}										\
										\
__TK_DLIST_UNUSED								\
static struct ElemType *							\
LT##_Last(LT *head)								\
{										\
    assert(head);								\
    return head->last;								\
}										\
										\
__TK_DLIST_UNUSED								\
static struct ElemType *							\
LT##_Next(struct ElemType *elem)						\
{										\
    assert(elem);								\
    return LT##_IsLast(elem) ? NULL : elem->_dl_.next;				\
}										\
										\
__TK_DLIST_UNUSED								\
static struct ElemType *							\
LT##_Prev(struct ElemType *elem)						\
{										\
    assert(elem);								\
    return LT##_IsFirst(elem) ? NULL : elem->_dl_.prev;				\
}										\
										\
__TK_DLIST_UNUSED								\
static unsigned									\
LT##_Size(const LT *head)							\
{										\
    const struct ElemType *elem;						\
    unsigned size = 0;								\
    assert(head);								\
    if ((elem = head->first)) {							\
	for ( ; elem != (void *) head; elem = elem->_dl_.next) {		\
	    ++size;								\
	}									\
    }										\
    return size;								\
}										\
										\
__TK_DLIST_UNUSED								\
static void									\
LT##_InsertAfter(struct ElemType *listElem, struct ElemType *elem)		\
{										\
    assert(listElem);								\
    assert(elem);								\
    elem->_dl_.next = listElem->_dl_.next;					\
    elem->_dl_.prev = listElem;							\
    listElem->_dl_.next->_dl_.prev = elem;					\
    listElem->_dl_.next = elem;							\
}										\
										\
__TK_DLIST_UNUSED								\
static void									\
LT##_InsertBefore(struct ElemType *listElem, struct ElemType *elem)		\
{										\
    assert(listElem);								\
    assert(elem);								\
    elem->_dl_.next = listElem;							\
    elem->_dl_.prev = listElem->_dl_.prev;;					\
    listElem->_dl_.prev->_dl_.next = elem;					\
    listElem->_dl_.prev = elem;							\
}										\
										\
__TK_DLIST_UNUSED								\
static void									\
LT##_Prepend(LT *head, struct ElemType *elem)					\
{										\
    assert(head);								\
    assert(elem);								\
    elem->_dl_.prev = (PSEntry *) head;						\
    if (!head->first) {								\
	elem->_dl_.next = (PSEntry *) head;					\
	head->last = elem;							\
    } else {									\
	elem->_dl_.next = head->first;						\
	head->first->_dl_.prev = elem;						\
    }										\
    head->first = elem;								\
}										\
										\
__TK_DLIST_UNUSED								\
static void									\
LT##_Append(LT *head, struct ElemType *elem)					\
{										\
    assert(head);								\
    assert(elem);								\
    elem->_dl_.next = (PSEntry *) head;						\
    if (!head->first) {								\
	elem->_dl_.prev = (PSEntry *) head;					\
	head->first = elem;							\
    } else {									\
	elem->_dl_.prev = head->last;						\
	head->last->_dl_.next = elem;						\
    }										\
    head->last = elem;								\
}										\
										\
__TK_DLIST_UNUSED								\
static void									\
LT##_Move(LT *dst, LT *src)							\
{										\
    assert(dst);								\
    assert(src);								\
    if (src->first) {								\
	if (dst->first) {							\
	    dst->last->_dl_.next = src->first;					\
	    src->first->_dl_.prev = dst->last;					\
	    dst->last = src->last;						\
	} else {								\
	    *dst = *src;							\
	    dst->first->_dl_.prev = (PSEntry *) dst;				\
	}									\
	dst->last->_dl_.next = (PSEntry *) dst;					\
	LT##_Init(src);								\
    }										\
}										\
										\
__TK_DLIST_UNUSED								\
static void									\
LT##_Remove(struct ElemType *elem)						\
{										\
    int isFirst, isLast;							\
    assert(LT##_IsLinked(elem));						\
    isFirst = LT##_IsFirst(elem);						\
    isLast = LT##_IsLast(elem);							\
    if (isFirst && isLast) {							\
	((LT *) elem->_dl_.prev)->first = NULL;					\
	((LT *) elem->_dl_.next)->last = NULL;					\
    } else {									\
	if (isFirst) {								\
	    ((LT *) elem->_dl_.prev)->first = elem->_dl_.next;			\
	} else {								\
	    elem->_dl_.prev->_dl_.next = elem->_dl_.next;			\
	}									\
	if (isLast) {								\
	    ((LT *) elem->_dl_.next)->last = elem->_dl_.prev;			\
	} else {								\
	    elem->_dl_.next->_dl_.prev = elem->_dl_.prev;			\
	}									\
    }										\
    LT##_ElemInit(elem);							\
}										\
										\
__TK_DLIST_UNUSED								\
static void									\
LT##_Free(struct ElemType *elem)						\
{										\
    LT##_Remove(elem);								\
    ckfree((void *) elem);							\
}										\
										\
__TK_DLIST_UNUSED								\
static void									\
LT##_RemoveHead(LT *head)							\
{										\
    assert(!LT##_IsEmpty(head));						\
    LT##_Remove(head->first);							\
}										\
										\
__TK_DLIST_UNUSED								\
static void									\
LT##_RemoveTail(LT *head)							\
{										\
    assert(!LT##_IsEmpty(head));						\
    LT##_Remove(head->last);							\
}										\
										\
__TK_DLIST_UNUSED								\
static void									\
LT##_FreeHead(LT *head)								\
{										\
    assert(!LT##_IsEmpty(head));						\
    LT##_Free(head->first);							\
}										\
										\
__TK_DLIST_UNUSED								\
static void									\
LT##_FreeTail(LT *head)								\
{										\
    assert(!LT##_IsEmpty(head));						\
    LT##_Free(head->last);							\
}										\
										\
__TK_DLIST_UNUSED								\
static void									\
LT##_SwapElems(struct ElemType *lhs, struct ElemType *rhs)			\
{										\
    assert(lhs);								\
    assert(rhs);								\
    if (lhs != rhs) {								\
	struct ElemType tmp;							\
	if (LT##_IsFirst(lhs))  {						\
	    ((LT *) lhs->_dl_.prev)->first = rhs;				\
	} else if (LT##_IsFirst(rhs)) {						\
	    ((LT *) rhs->_dl_.prev)->first = lhs;				\
	}									\
	if (LT##_IsLast(lhs))  {						\
	    ((LT *) lhs->_dl_.next)->last = rhs;				\
	} else if (LT##_IsLast(rhs)) {						\
	    ((LT *) rhs->_dl_.next)->last = lhs;				\
	}									\
	tmp._dl_ = lhs->_dl_;							\
	lhs->_dl_ = rhs->_dl_;							\
	rhs->_dl_ = tmp._dl_;							\
    }										\
}										\
										\
__TK_DLIST_UNUSED								\
static void									\
LT##_Clear(LT *head)								\
{										\
    struct ElemType *p;								\
    struct ElemType *next;							\
    assert(head);								\
    for (p = head->first; p; p = next) {					\
	next = LT##_Next(p);							\
	ckfree((void *) p);							\
    }										\
    LT##_Init(head);								\
}										\
										\
__TK_DLIST_UNUSED								\
static void									\
LT##_Traverse(LT *head, LT##_Func func)						\
{										\
    struct ElemType *next;							\
    struct ElemType *p;								\
    assert(head);								\
    for (p = head->first; p; p = next) {					\
	next = func(head, p);							\
    }										\
}										\
/* ------------------------------------------------------------------------- */

#define TK_DLIST_FOREACH(var, head)						\
    assert(head);								\
    for (var = head->first ? head->first : (PSEntry *) head; var != (PSEntry *) head; var = var->_dl_.next)

#define TK_DLIST_FOREACH_REVERSE(var, head)					\
    assert(head);								\
    for (var = head->last ? head->last : (PSEntry *) head; var != (PSEntry *) head; var = var->_dl_.prev)

#endif /* TK_DLIST_DEFINED */

/*
 * Local Variables:
 * mode: c
 * c-basic-offset: 4
 * fill-column: 105
 * End:
 * vi:set ts=8 sw=4:
 */
