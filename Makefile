SRCS = awb alsa engine event

%.o : %.cc
	mkdir -p .deps
	g++ -c $*.cc -g -MD  -MF .deps/$*.d -o $*.o

awbd : $(foreach f,$(SRCS),$f.o)
	g++ $^ -lspug++ -lasound -o awbd

-include $(foreach f,$(SRCS),.deps/$f.d)
