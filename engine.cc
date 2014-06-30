
#include "engine.h"
#include "event.h"

#include <iostream>

using namespace awb;
using namespace std;

void DebugDispatcher::onEvent(Event *event) {
    cout << "Got event " << *event << endl;
}
