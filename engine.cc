
#include "engine.h"

#include <iostream>

#include <spug/Reactor.h>
#include <spug/Time.h>
#include <spug/TimeDelta.h>

#include "event.h"

using namespace awb;
using namespace mawb;
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

TrackPtr InputDispatcher::releaseTrack() {
    TrackPtr result = track;
    track = 0;
    return result;
}

void InputDispatcher::beginRecording() {
    track = new Track();
}

static const int MILLION = 1000000;

uint32 TimeMaster::getTicks() {
    Time now = Time::now();
    TimeDelta delta = now - lastAbsTime;
    int64 longTime = delta.getSeconds() * MILLION + delta.getMicroseconds();
    int64 ticksDelta = (longTime * bpm * ppb) / (60 * MILLION);

    // We don't want to advance the last absolute time if difference is too
    // small to advance the tick counter.
    if (ticksDelta > 0) {
        lastAbsTime = now;
        lastTicks += ticksDelta;
    }

    return lastTicks;
}

TimeDelta TimeMaster::ticksAsTimeDelta(uint32 ticks) const {
    int64 longTime = (ticks * 60 * MILLION) / (bpm * ppb);
    return TimeDelta(longTime / MILLION, longTime % MILLION);
}

void TimeMaster::setTicks(uint32 time) {
    lastTicks = time;
    lastAbsTime = Time::now();
}

Controller::Controller(Reactor &reactor, TimeMaster &timeMaster) :
    reactor(reactor),
    timeMaster(timeMaster) {
}

void Controller::setState(mawb::SequencerState newState) {
    if (state == RECORD)
        storeInputTracks();

    switch (newState) {
        case IDLE:
            break;
        case RECORD:
            beginRecording();
            // fall through.
        case PLAY:
        case LATCHED_RECORD:
            state = newState;
            runOnce();
            break;
        default:
            cerr << "Unknown state received: " << newState << endl;
            return;
    }

    state = newState;
}

void Controller::storeInputTracks() {
    for (int i = 0; i < inputs.size(); ++i) {
        TrackPtr track = inputs[i]->releaseTrack();
        if (track && track->size())
            tracks.push_back(TrackInfo(track.get(), inputs[i]->getConsumer()));
    }
}

void Controller::beginRecording() {
    for (int i = 0; i < inputs.size(); ++i)
        inputs[i]->beginRecording();
}

void Controller::setTicks(uint32 time) {
    timeMaster.setTicks(time);

    // For each track, find the first event that is later than the new time
    // and set the "next" pointer to it.
    for (int i = 0; i < tracks.size(); ++i) {
        TrackInfo &ti = tracks[i];
        int j;
        for (j = 0; j < ti.track->size(); ++j) {
            if (ti.track->get(j)->time > time)
                break;
        }
        ti.next = j;
    }
}

static const uint32 NEVER = 0xffffffff;

namespace {

    // Wraps a Runnable so the reactor doesn't delete it after it's de-queued.
    struct RunnableWrapper : public Runnable {
        Runnable *wrapped;
        RunnableWrapper(Runnable *wrapped) : wrapped(wrapped) {}
        virtual void run() { wrapped->run(); }
    };
}

void Controller::runOnce() {
    if (state == IDLE)
        return;

    uint32 time = timeMaster.getTicks();
//    cerr << "running at " << time << endl;
    uint32 nextTime = NEVER;
    if (state == PLAY || state == RECORD || state == LATCHED_RECORD) {
        for (int i = 0; i < tracks.size(); ++i) {
            TrackInfo &ti = tracks[i];

            // Ignore if we're past the end. TODO: add support for looping.
            if (ti.next >= ti.track->size())
                continue;

            // Play all events that are due to be played.
            Event *event = ti.track->get(ti.next).get();
            while (time >= event->time) {
//                cerr << "playing event " << *event << endl;
                ti.dispatcher->onEvent(event);
                ti.next++;
                if (ti.next >= ti.track->size()) {
                    event = 0;
                    break;
                }

                event = ti.track->get(ti.next).get();
            }

            // See if the next event is the next one we want to schedule.
            if (event && event->time < nextTime)
                nextTime = event->time;
        }
    }

    // If there are no more events pending, switch to IDLE mode.
    if (nextTime == NEVER && state == PLAY) {
//        cerr << "back to idle" << endl;
        state = IDLE;
    } else {
        // Schedule the callback for the next event.
        reactor.schedule(timeMaster.ticksAsTimeDelta(nextTime - time),
                         new RunnableWrapper(this)
                         );
    }
}

void Controller::run() {
    runOnce();
}
