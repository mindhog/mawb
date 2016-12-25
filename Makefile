SRCS = awb alsa engine event fluid mawb.pb

%.o : %.cc mawb.pb.h
	mkdir -p .deps
	g++ -c $*.cc  -std=c++11 -g -MD  -MF .deps/$*.d -o $*.o

all : awbd mawb_pb2.py

check : event_test
	event_test

awbd : $(foreach f,$(SRCS),$f.o)
	g++ $^ -lspug++ -lasound -lfluidsynth -lprotobuf -o awbd

jawbd : jackengine.o
	g++ $^ -std=c++11 -ljack -o jawbd

mawb_pb2.py mawb.pb.cc mawb.pb.h : mawb.proto
	protoc --cpp_out=. --python_out=. mawb.proto

event_test : event_test.o event.o
	g++ $^ -g -lspug++ -o event_test

-include $(foreach f,$(SRCS),.deps/$f.d)
