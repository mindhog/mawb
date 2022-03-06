
%module(threads = 1) alsa_mixer
%nothread;

%include "typemaps.i"
%include "carrays.i"
%include "cmalloc.i"

%{
#include <alsa/asoundlib.h>
#include <alsa/mixer.h>
%}

// In order to convert Type** output arguments to return values, we need to
// define both an input typemap and an argout typemap.  We can then apply both
// of these to the various types that we need to do this for.
%typemap(in, numinputs = 0) INPUT ** (void *result) {
  $1 = ($1_type)&result;
}

%typemap(argout) ARGOUT ** {
    $result = SWIG_Python_AppendOutput(
        $result,
        SWIG_NewPointerObj(SWIG_as_voidptr(*$1),
                           $*1_descriptor,
                           0
                           )
    );
}

%apply INPUT ** { snd_mixer_t ** }
%apply ARGOUT ** { snd_mixer_t ** }
%apply INPUT ** { snd_mixer_selem_id_t ** }
%apply ARGOUT ** { snd_mixer_selem_id_t ** }

// The mixer functions use a long* return argument to return parameter values.
%typemap(in, numinputs = 0) long * (void *result) {
  $1 = ($1_type)&result;
}

%typemap(argout) long * {
    $result = SWIG_Python_AppendOutput(
        $result,
        SWIG_From_long(*$1)
    );
}

// Simlilarly, for functions returning a min and max we identify a special
// two-argument form.
// It was very hard to get this right.  To make this work, you have to not
// specify argument names in the first pair of definitions ("long *, long *")
// and then provide a single temporary variable ("long temp") for the local
// vars.  The local variable will be generated once for each of the arguments.
// Specifying the argument names in the first pair of definitions breaks this
// for some reason.

%typemap(in, numinputs = 0) long *, long * (long temp) {
  $1 = ($1_type)&temp;
}

%typemap(argout) long *min, long *max {
    $result = SWIG_Python_AppendOutput(
        $result,
        SWIG_From_long(*$1)
    );
}


%include "/usr/include/alsa/mixer.h"
