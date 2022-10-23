
%module(threads = 1) lilv
%nothread;

%include "typemaps.i"
%include "carrays.i"
%include "cmalloc.i"

%{
#include "lilv-0/lilv/lilv.h"
#include <alloca.h>
%}

%typemap(out) uint32_t {
    $result = PyInt_FromLong($1);
}

%typemap(in) uint32_t {
    $1 = PyInt_AsLong($input);
}

// ignore the input operators.
%typemap(in, numinputs=0) (LilvNode **deflt, LilvNode** min, LilvNode** max) {
    LilvNode **temp = alloca(sizeof(LilvNode *));
    $1 = &temp[0];
    $2 = &temp[1];
    $3 = &temp[2];
}

%typemap(argout) (LilvNode **deflt, LilvNode** min, LilvNode** max) {
    PyObject *r = PyTuple_New(3);
    PyObject *val = *$1 ? PyFloat_FromDouble(lilv_node_as_float(*$1)) :
                          SWIG_Py_Void();
    PyTuple_SET_ITEM(r, 0, val);
    val = *$2 ? PyFloat_FromDouble(lilv_node_as_float(*$2)) :
                                SWIG_Py_Void();
    PyTuple_SET_ITEM(r, 1, val);
    val = (bool)*$3 ? PyFloat_FromDouble(lilv_node_as_float(*$3)) :
                      SWIG_Py_Void();
    PyTuple_SET_ITEM(r, 2, val);
    $result = r;
}

%ignore lilv_plugin_get_num_ports_of_class_va;

%include "/usr/include/lilv-0/lilv/lilv.h"
