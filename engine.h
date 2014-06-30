#ifndef awb_engine_h_
#define awb_engine_h_

namespace awb {

class Event;

// Abstract class that is associated with an event source.  Implementations
// should control processing of the event.
class EventDispatcher {
    public:
        virtual void onEvent(Event *event) = 0;
};

class DebugDispatcher : public EventDispatcher {
    public:
        virtual void onEvent(Event *event);
};

}

#endif
