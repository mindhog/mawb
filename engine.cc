
#include "engine.h"

#include <iostream>

#include <spug/Time.h>
#include <spug/TimeDelta.h>

#include "event.h"

using namespace awb;
using namespace spug;
using namespace std;

void DebugDispatcher::onEvent(Event *event) {
    cout << "Got event " << *event << endl;
}

void InputDispatcher::onEvent(Event *event) {
    uint32 t = timeMaster->getTicks();
    event->time = t;
    if (track)
        track->add(event);
    if (consumer)
        consumer->onEvent(event);
}

InputDispatcher::InputDispatcher(TimeMaster *timeMaster, Track *recordTrack,
                                 EventDispatcher *consumer
                                 ) :
    timeMaster(timeMaster),
    track(recordTrack),
    consumer(consumer) {
}

void InputDispatcher::setRecordTrack(Track *track) {
    this->track = track;
}

uint32 TimeMaster::getTicks() const {
    Time now = Time::now();
    TimeDelta delta = now - lastAbsTime;
    int64 longTime = delta.getSeconds() * 1000000 + delta.getMicroseconds();
    return (longTime * bpm * ppb) / (60 * 1000000);
}
