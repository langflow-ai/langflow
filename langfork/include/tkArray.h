/*
 * tkArray.h --
 *
 * An array is a sequence of items, stored in a contiguous memory region.
 * Random access to any item is very fast. New items can be either appended
 * or prepended. An array may be traversed in the forward or backward direction.
 *
 * Copyright (c) 2018-2019 Gregor Cramer.
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
 * Use the array in the following way:
 * -------------------------------------------------------------------------------
 * typedef struct { int key, value; } Pair;
 * TK_PTR_ARRAY_DEFINE(MyArray, Pair);
 * MyArray *arr = NULL;
 * if (MyArray_IsEmpty(arr)) {
 *     MyArray_Append(&arr, MakePair(1, 2));
 *     MyArray_Append(&arr, MakePair(2, 3));
 *     for (i = 0; i < MyArray_Size(arr); ++i) {
 *         Pair *p = MyArray_Get(arr, i);
 *         printf("%d -> %d\n", p->key, p->value);
 *         ckfree(p);
 *     }
 *     MyArray_Free(&arr);
 *     assert(arr == NULL);
 * }
 * -------------------------------------------------------------------------------
 * Or with aggregated elements:
 * -------------------------------------------------------------------------------
 * typedef struct { int key, value; } Pair;
 * TK_ARRAY_DEFINE(MyArray, Pair);
 * Pair p1 = { 1, 2 };
 * Pair p2 = { 2, 3 };
 * MyArray *arr = NULL;
 * if (MyArray_IsEmpty(arr)) {
 *     MyArray_Append(&arr, p1);
 *     MyArray_Append(&arr, p2);
 *     for (i = 0; i < MyArray_Size(arr); ++i) {
 *         const Pair *p = MyArray_Get(arr, i);
 *         printf("%d -> %d\n", p->key, p->value);
 *     }
 *     MyArray_Free(&arr);
 *     assert(arr == NULL);
 * }
 * -------------------------------------------------------------------------------
 */

/*************************************************************************/
/*
 * Two array types will be provided:
 * Use TK_ARRAY_DEFINE if your array is aggregating the elements. Use
 * TK_PTR_ARRAY_DEFINE if your array contains pointers to elements. But
 * in latter case the array is not responsible for the lifetime of the
 * elements.
 */
/*************************************************************************/
/*
 * Array_ElemSize: Returns the memory size for one array element.
 */
/*************************************************************************/
/*
 * Array_BufferSize: Returns the memory size for given number of elements.
 */
/*************************************************************************/
/*
 * Array_IsEmpty: Array is empty?
 */
/*************************************************************************/
/*
 * Array_Size: Number of elements in array.
 */
/*************************************************************************/
/*
 * Array_Capacity: Capacity of given array. This is the maximal number of
 * elements fitting into current array memory without resizing the buffer.
 */
/*************************************************************************/
/*
 * Array_SetSize: Set array size, new size must not exceed the capacity of
 * the array. This function has to be used with care when increasing the
 * array size.
 */
/*************************************************************************/
/*
 * Array_First: Returns position of first element in array. Given array
 * may be NULL.
 */
/*************************************************************************/
/*
 * Array_Last: Returns position after last element in array. Given array
 * may be empty.
 */
/*************************************************************************/
/*
 * Array_Front: Returns first element in array. Given array must not be
 * empty.
 */
/*************************************************************************/
/*
 * Array_Back: Returns last element in array. Given array must not be
 * empty.
 */
/*************************************************************************/
/*
 * Array_Resize: Resize buffer of array for given number of elements. The
 * array may grow or shrink. Note that this function is not initializing
 * the increased buffer.
 */
/*************************************************************************/
/*
 * Array_ResizeAndClear: Resize buffer of array for given number of
 * elements. The array may grow or shrink. The increased memory will be
 * filled with zeroes.
 */
/*************************************************************************/
/*
 * Array_Clear: Fill specified range with zeroes.
 */
/*************************************************************************/
/*
 * Array_Free: Resize array to size zero. This function will release the
 * array buffer.
 */
/*************************************************************************/
/*
 * Array_Append: Insert given element after end of array.
 */
/*************************************************************************/
/*
 * Array_PopBack: Shrink array by one element. Given array must not be
 * empty.
 */
/*************************************************************************/
/*
 * Array_Get: Random access to array element at given position. The given
 * index must not exceed current array size.
 */
/*************************************************************************/
/*
 * Array_Set: Replace array element at given position with new value. The
 * given index must not exceed current array size.
 */
/*************************************************************************/
/*
 * Array_Find: Return index position of element which matches given
 * argument. If not found then -1 will be returned.
 */
/*************************************************************************/

#ifndef TK_ARRAY_DEFINED
#define TK_ARRAY_DEFINED

#include "tkInt.h"

#if defined(__GNUC__) || defined(__clang__)
# define __TK_ARRAY_UNUSED __attribute__((unused))
#else
# define __TK_ARRAY_UNUSED
#endif

#define TK_ARRAY_DEFINE(AT, ElemType) /* AT = type of array */			\
/* ------------------------------------------------------------------------- */	\
typedef struct AT {								\
    size_t size;								\
    size_t capacity;								\
    ElemType buf[1];								\
} AT;										\
										\
__TK_ARRAY_UNUSED								\
static void									\
AT##_Init(AT *arr)								\
{										\
    assert(arr);								\
    arr->size = 0;								\
    arr->capacity = 0;								\
}										\
										\
__TK_ARRAY_UNUSED								\
static size_t									\
AT##_ElemSize(void)									\
{										\
    return sizeof(ElemType);							\
}										\
										\
__TK_ARRAY_UNUSED								\
static size_t									\
AT##_BufferSize(size_t numElems)						\
{										\
    return numElems*sizeof(ElemType);						\
}										\
										\
__TK_ARRAY_UNUSED								\
static int									\
AT##_IsEmpty(const AT *arr)							\
{										\
    assert(!arr || arr->size != 0xdeadbeef);					\
    return !arr || arr->size == 0u;						\
}										\
										\
__TK_ARRAY_UNUSED								\
static size_t									\
AT##_Size(const AT *arr)							\
{										\
    assert(!arr || arr->size != 0xdeadbeef);					\
    return arr ? arr->size : 0u;						\
}										\
										\
__TK_ARRAY_UNUSED								\
static size_t									\
AT##_Capacity(const AT *arr)							\
{										\
    assert(!arr || arr->size != 0xdeadbeef);					\
    return arr ? arr->capacity : 0u;						\
}										\
										\
__TK_ARRAY_UNUSED								\
static ElemType *								\
AT##_First(AT *arr)								\
{										\
    assert(!arr || arr->size != 0xdeadbeef);					\
    return arr ? arr->buf : NULL;						\
}										\
										\
__TK_ARRAY_UNUSED								\
static ElemType *								\
AT##_Last(AT *arr)								\
{										\
    assert(!arr || arr->size != 0xdeadbeef);					\
    return arr ? arr->buf + arr->size : NULL;					\
}										\
										\
__TK_ARRAY_UNUSED								\
static ElemType *								\
AT##_Front(AT *arr)								\
{										\
    assert(arr);								\
    assert(arr->size != 0xdeadbeef);						\
    assert(!AT##_IsEmpty(arr));							\
    return &arr->buf[0];							\
}										\
										\
__TK_ARRAY_UNUSED								\
static ElemType *								\
AT##_Back(AT *arr)								\
{										\
    assert(arr);								\
    assert(arr->size != 0xdeadbeef);						\
    assert(!AT##_IsEmpty(arr));							\
    return &arr->buf[arr->size - 1];						\
}										\
										\
__TK_ARRAY_UNUSED								\
static void									\
AT##_Resize(AT **arrp, size_t newSize)						\
{										\
    assert(arrp);								\
    assert(!*arrp || (*arrp)->size != 0xdeadbeef);				\
    if (newSize == 0) {								\
	assert(!*arrp || ((*arrp)->size = 0xdeadbeef));				\
	ckfree(*arrp);								\
	*arrp = NULL;								\
    } else {									\
	int init = *arrp == NULL;						\
	size_t memSize = AT##_BufferSize(newSize - 1) + sizeof(AT);		\
	*arrp = (AT *)ckrealloc(*arrp, memSize);					\
	if (init) {								\
	    (*arrp)->size = 0;							\
	} else if (newSize < (*arrp)->size) {					\
	    (*arrp)->size = newSize;						\
	}									\
	(*arrp)->capacity = newSize;						\
    }										\
}										\
										\
__TK_ARRAY_UNUSED								\
static void									\
AT##_Clear(AT *arr, size_t from, size_t to)					\
{										\
    assert(arr);								\
    assert(arr->size != 0xdeadbeef);						\
    assert(to <= AT##_Capacity(arr));						\
    assert(from <= to);								\
    memset(arr->buf + from, 0, AT##_BufferSize(to - from));			\
}										\
										\
__TK_ARRAY_UNUSED								\
static void									\
AT##_ResizeAndClear(AT **arrp, size_t newSize)					\
{										\
    size_t oldCapacity;								\
    assert(arrp);								\
    oldCapacity = *arrp ? (*arrp)->capacity : 0;				\
    AT##_Resize(arrp, newSize);							\
    if (newSize > oldCapacity) {						\
	AT##_Clear(*arrp, oldCapacity, newSize);				\
    }										\
}										\
										\
__TK_ARRAY_UNUSED								\
static void									\
AT##_SetSize(AT *arr, size_t newSize)						\
{										\
    assert(newSize <= AT##_Capacity(arr));					\
    assert(!arr || arr->size != 0xdeadbeef);					\
    if (arr) {									\
	arr->size = newSize;							\
    }										\
}										\
										\
__TK_ARRAY_UNUSED								\
static void									\
AT##_Append(AT **arrp, ElemType *elem)						\
{										\
    assert(arrp);								\
    if (!*arrp) {								\
	AT##_Resize(arrp, 1);							\
    } else if ((*arrp)->size == (*arrp)->capacity) {				\
	AT##_Resize(arrp, (*arrp)->capacity + ((*arrp)->capacity + 1)/2);	\
    }										\
    (*arrp)->buf[(*arrp)->size++] = *elem;					\
}										\
										\
__TK_ARRAY_UNUSED								\
static size_t									\
AT##_PopBack(AT *arr)								\
{										\
    assert(!AT##_IsEmpty(arr));							\
    return arr->size -= 1;							\
}										\
										\
__TK_ARRAY_UNUSED								\
static ElemType *								\
AT##_Get(const AT *arr, size_t at)						\
{										\
    assert(arr);								\
    assert(at < AT##_Size(arr));						\
    return (ElemType *) &arr->buf[at];						\
}										\
										\
__TK_ARRAY_UNUSED								\
static void									\
AT##_Set(AT *arr, size_t at, ElemType *elem)					\
{										\
    assert(arr);								\
    assert(at < AT##_Size(arr));						\
    arr->buf[at] = *elem;							\
}										\
										\
__TK_ARRAY_UNUSED								\
static void									\
AT##_Free(AT **arrp)								\
{										\
    AT##_Resize(arrp, 0);							\
}										\
										\
__TK_ARRAY_UNUSED								\
static int									\
AT##_Find(const AT *arr, const ElemType *elem)					\
{										\
    assert(!arr || arr->size != 0xdeadbeef);					\
    if (arr) {									\
	const ElemType *buf = arr->buf;						\
	size_t i;								\
	for (i = 0; i < arr->size; ++i) {					\
	    if (memcmp(&buf[i], elem, sizeof(ElemType)) == 0) {			\
		return (int) i;							\
	    }									\
	}									\
    }										\
    return -1;									\
}										\
										\
__TK_ARRAY_UNUSED								\
static int									\
AT##_Contains(const AT *arr, const ElemType *elem)				\
{										\
    return AT##_Find(arr, elem) != -1;						\
}										\
/* ------------------------------------------------------------------------- */

#define TK_PTR_ARRAY_DEFINE(AT, ElemType) /* AT = type of array */		\
/* ------------------------------------------------------------------------- */	\
typedef struct AT {								\
    size_t size;								\
    size_t capacity;								\
    ElemType *buf[1];								\
} AT;										\
										\
__TK_ARRAY_UNUSED								\
static size_t									\
AT##_ElemSize(void)									\
{										\
    return sizeof(ElemType);							\
}										\
										\
__TK_ARRAY_UNUSED								\
static size_t									\
AT##_BufferSize(size_t numElems)						\
{										\
    return numElems*sizeof(ElemType *);						\
}										\
										\
__TK_ARRAY_UNUSED								\
static int									\
AT##_IsEmpty(const AT *arr)							\
{										\
    assert(!arr || arr->size != 0xdeadbeef);					\
    return !arr || arr->size == 0;						\
}										\
										\
__TK_ARRAY_UNUSED								\
static ElemType **								\
AT##_First(AT *arr)								\
{										\
    assert(!arr || arr->size != 0xdeadbeef);					\
    return arr ? arr->buf : NULL;						\
}										\
										\
__TK_ARRAY_UNUSED								\
static ElemType **								\
AT##_Last(AT *arr)								\
{										\
    assert(!arr || arr->size != 0xdeadbeef);					\
    return arr ? arr->buf + arr->size : NULL;					\
}										\
										\
__TK_ARRAY_UNUSED								\
static ElemType *								\
AT##_Front(AT *arr)								\
{										\
    assert(arr);								\
    assert(arr->size != 0xdeadbeef);						\
    assert(!AT##_IsEmpty(arr));							\
    return arr->buf[0];								\
}										\
										\
__TK_ARRAY_UNUSED								\
static ElemType *								\
AT##_Back(AT *arr)								\
{										\
    assert(arr);								\
    assert(arr->size != 0xdeadbeef);						\
    assert(!AT##_IsEmpty(arr));							\
    return arr->buf[arr->size - 1];						\
}										\
										\
__TK_ARRAY_UNUSED								\
static size_t									\
AT##_Size(const AT *arr)							\
{										\
    assert(!arr || arr->size != 0xdeadbeef);					\
    return arr ? arr->size : 0;							\
}										\
										\
__TK_ARRAY_UNUSED								\
static size_t									\
AT##_Capacity(const AT *arr)							\
{										\
    assert(!arr || arr->size != 0xdeadbeef);					\
    return arr ? arr->capacity : 0;						\
}										\
										\
__TK_ARRAY_UNUSED								\
static void									\
AT##_Resize(AT **arrp, size_t newCapacity)					\
{										\
    assert(arrp);								\
    assert(!*arrp || (*arrp)->size != 0xdeadbeef);				\
    if (newCapacity == 0) {							\
	assert(!*arrp || ((*arrp)->size = 0xdeadbeef));				\
	ckfree(*arrp);								\
	*arrp = NULL;								\
    } else {									\
	int init = *arrp == NULL;						\
	size_t memSize = AT##_BufferSize(newCapacity - 1) + sizeof(AT);		\
	*arrp = (AT *)ckrealloc(*arrp, memSize);					\
	if (init) {								\
	    (*arrp)->size = 0;							\
	} else if (newCapacity < (*arrp)->size) {				\
	    (*arrp)->size = newCapacity;					\
	}									\
	(*arrp)->capacity = newCapacity;					\
    }										\
}										\
										\
__TK_ARRAY_UNUSED								\
static void									\
AT##_Clear(AT *arr, size_t from, size_t to)					\
{										\
    assert(arr);								\
    assert(arr->size != 0xdeadbeef);						\
    assert(to <= AT##_Capacity(arr));						\
    assert(from <= to);								\
    memset(arr->buf + from, 0, AT##_BufferSize(to - from));			\
}										\
										\
__TK_ARRAY_UNUSED								\
static void									\
AT##_ResizeAndClear(AT **arrp, size_t newCapacity)				\
{										\
    size_t oldCapacity;								\
    assert(arrp);								\
    oldCapacity = *arrp ? (*arrp)->capacity : 0;				\
    AT##_Resize(arrp, newCapacity);						\
    if (newCapacity > oldCapacity) {						\
	AT##_Clear(*arrp, oldCapacity, newCapacity);				\
    }										\
}										\
										\
__TK_ARRAY_UNUSED								\
static void									\
AT##_SetSize(AT *arr, size_t newSize)						\
{										\
    assert(arr);								\
    assert(newSize <= AT##_Capacity(arr));					\
    arr->size = newSize;							\
}										\
										\
__TK_ARRAY_UNUSED								\
static void									\
AT##_Append(AT **arrp, ElemType *elem)						\
{										\
    assert(arrp);								\
    if (!*arrp) {								\
	AT##_Resize(arrp, 1);							\
    } else if ((*arrp)->size == (*arrp)->capacity) {				\
	AT##_Resize(arrp, (*arrp)->capacity + ((*arrp)->capacity + 1)/2);	\
    }										\
    (*arrp)->buf[(*arrp)->size++] = elem;					\
}										\
										\
__TK_ARRAY_UNUSED								\
static size_t									\
AT##_PopBack(AT *arr)								\
{										\
    assert(!AT##_IsEmpty(arr));							\
    return arr->size -= 1;							\
}										\
										\
__TK_ARRAY_UNUSED								\
static ElemType *								\
AT##_Get(const AT *arr, size_t at)						\
{										\
    assert(arr);								\
    assert(at < AT##_Size(arr));						\
    return arr->buf[at];							\
}										\
										\
__TK_ARRAY_UNUSED								\
static void									\
AT##_Set(AT *arr, size_t at, ElemType *elem)					\
{										\
    assert(arr);								\
    assert(at < AT##_Size(arr));						\
    arr->buf[at] = elem;							\
}										\
										\
__TK_ARRAY_UNUSED								\
static void									\
AT##_Free(AT **arrp)								\
{										\
    AT##_Resize(arrp, 0);							\
}										\
										\
__TK_ARRAY_UNUSED								\
static int									\
AT##_Find(const AT *arr, const ElemType *elem)					\
{										\
    assert(!arr || arr->size != 0xdeadbeef);					\
    if (arr) {									\
	ElemType *const *buf = arr->buf;					\
	size_t i;								\
	for (i = 0; i < arr->size; ++i) {					\
	    if (buf[i] == elem) {						\
		return (int) i;							\
	    }									\
	}									\
    }										\
    return -1;									\
}										\
										\
__TK_ARRAY_UNUSED								\
static int									\
AT##_Contains(const AT *arr, const ElemType *elem)				\
{										\
    return AT##_Find(arr, elem) != -1;						\
}										\
/* ------------------------------------------------------------------------- */

#endif /* TK_ARRAY_DEFINED */

/*
 * Local Variables:
 * mode: c
 * c-basic-offset: 4
 * fill-column: 105
 * End:
 * vi:set ts=8 sw=4:
 */
