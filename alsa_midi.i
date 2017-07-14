
%module(threads = 1) alsa_midi
%nothread;

%include "typemaps.i"
%include "carrays.i"
%include "cmalloc.i"

// Fake out swig to get some useful macros.
void snd_seq_ev_set_source(snd_seq_event_t *event, int port);
void snd_seq_ev_set_direct(snd_seq_event_t *event);
void snd_seq_ev_set_subs(snd_seq_event_t *event);
void snd_seq_ev_set_fixed(snd_seq_event_t *event);

// Release the GIL when blocked on an event input.
%thread snd_seq_event_input;

%{
#include <alsa/asoundlib.h>
#include <alsa/seq_event.h>
#include <poll.h>   // to get pollfd

snd_seq_event_t *snd_seq_event_t_new(void) {
    return calloc(sizeof(snd_seq_event_t), 1);
}

typedef struct pollfd Pollfd;

%}

%array_class(Pollfd, PollfdArray);

// mapping to allow us to return the snd_seq_t ** object we've created.
%typemap(in, numinputs = 0) snd_seq_t ** (void *result) {
  $1 = ($1_type)&result;
}

%typemap(argout) snd_seq_t ** {
    $result = SWIG_Python_AppendOutput(
        $result, 
        SWIG_NewPointerObj(SWIG_as_voidptr(*$1), 
                           $*1_descriptor, 
                           0
                           )
    );
}

%typemap(in, numinputs = 0) snd_seq_query_subscribe_t ** (void *result) {
  $1 = ($1_type)&result;
}

%typemap(argout) snd_seq_query_subscribe_t ** {
    $result = SWIG_Python_AppendOutput(
        $result,
        SWIG_NewPointerObj(SWIG_as_voidptr(*$1),
                           $*1_descriptor,
                           0
                           )
    );
}

%apply snd_seq_t ** { snd_seq_client_info_t ** }
%apply snd_seq_t ** { snd_seq_port_info_t ** }
%apply snd_seq_t ** { snd_seq_port_subscribe_t ** }
%apply snd_seq_t ** { snd_seq_event_t ** }

// Just including the C definitions works for alsa, as long as we define
// __attribute__() so swig doesn't choke on it.
#define __attribute__(x)
%include "/usr/include/alsa/seq_event.h"
%include "/usr/include/alsa/seq.h"
%include "/usr/include/alsa/seqmid.h"

snd_seq_event_t *snd_seq_event_t_new();

// We have to reproduce this here, the definition probably isn't directly in
// poll.h.
typedef struct pollfd {
    int fd;
    short events;
    short revents;
} Pollfd;
