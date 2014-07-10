SRCS = awb alsa engine event fluid mawb.pb

%.o : %.cc
	mkdir -p .deps
	g++ -c $*.cc -g -MD  -MF .deps/$*.d -o $*.o

all : awbd mawb_pb2.py

awbd : $(foreach f,$(SRCS),$f.o)
	g++ $^ -lspug++ -lasound -lfluidsynth -lprotobuf -o awbd

mawb_pb2.py mawb.pb.cc mawb.pb.h : mawb.proto
	protoc --cpp_out=. --python_out=. mawb.proto

-include $(foreach f,$(SRCS),.deps/$f.d)
