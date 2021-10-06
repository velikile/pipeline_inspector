from sys import argv
import threading
from enum import Enum
import numpy as np
import gi

def import_gst():
#    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst, GLib,GObject
    return Gst, GLib, GObject

Gst, GLib , GObject = import_gst()
Gst.init(argv)

class GstProbeEvent(Enum):
    BUFFER           = (1 << 4),
    BUFFER_LIST      = (1 << 5),
    EVENT_DOWNSTREAM = (1 << 6),
    EVENT_UPSTREAM   = (1 << 7),
    EVENT_FLUSH      = (1 << 8),
    QUERY_DOWNSTREAM = (1 << 9),
    QUERY_UPSTREAM   = (1 << 10),


def loop():
    loop = GLib.MainLoop()
    try:
        loop.run()
    except:
        print("done")

class ProbeData:
    def __init__(self,gst_pipeline):
        self.gst_pipeline = gst_pipeline

class Sink:
    def __init__(self,name,sink = None):
        self.name = name
        self.sink = sink
        self.params = {}
class Src:
    def __init__(self,name,src = None):
        self.name = name
        self.src = src
        self.params = {}

class Metric:
    def __init__(self ,name, gst_element):
        self.name = name
        self.gst_element = gst_element
        self.gui_name = name
        self.gui_checked = False
        self.src_data = [(i,0) for i in range(400)]
        self.sink_data = [(i,0) for i in range(400)]
        self.src_data_index = 0
        self.sink_data_index = 0
        self.prev_src_data = None
        self.prev_sink_data = None
        self.buffer_ids = {}

    def push_data_src(self,data):
        if self.prev_src_data:
            self.src_data[self.src_data_index] = (data,data-self.prev_src_data)
            self.src_data_index = (self.src_data_index + 1) % len(self.src_data)
        self.prev_src_data = data

    def push_data_sink(self,data):
        if self.prev_sink_data:
            self.sink_data[self.sink_data_index] = (data,data - self.prev_sink_data)
            self.sink_data_index  =  (self.sink_data_index +  1) % len(self.sink_data)
        self.prev_sink_data = data

    def push_buffer_id(self,id,time):
        if id in self.buffer_ids :
           return False
        else :
            self.buffer_ids[id] = time
            return True

    def pop_buffer_id(self,id,time):
        if id in self.buffer_ids:
            self.buffer_ids.pop(id)
            return time
        return None

class Caps_template:
    def __init__(self,padname,direction,kvpairs):
        self.padname = padname
        self.direction = direction
        self.kvpairs = kvpairs
        self.gui_expanded = False
        self.gui_visible = True

class Processing_element:
    def __init__(self,id,pipeline=None,gst_element=None,params=None,srcs=None,sinks=None):
        self.pipeline = pipeline
        self.gst_element = gst_element
        self.sinks = [] if not sinks else sinks
        self.srcs =  [] if not srcs else srcs
        self.props=[]
        self.metrics =[Metric("Latency",gst_element),Metric("FrameTime",gst_element),Metric("Clock",gst_element)]
        self.params = {} if not params else params
        self.id = id
        self.gui_visible = True
        self.gui_expanded = False

    def set_name(self,name):
        self.name = name

    def connect(self,message_name,func,user_data):
        assert(self.gst_element)
        self.gst_element.connect(message_name,func,user_data)

    def on_new_sample(self,sink,user_data = None):
        sample = sink.emit('pull-sample')
        print(sample)
        return Gst.FlowReturn.OK

    def get_property(self,name):
        assert(self.gst_element)
        assert(name in self.params)
        return self.gst_element.get_property(name)

    def get_caps_templates(self):
        assert(self.gst_element)
        capstemplates = []
        templates = self.gst_element.get_pad_template_list()
        for t in templates:
            padname = t.get_name()
            direction = "SRC" if t.direction == Gst.PadDirection.SRC else "SINK" if t.direction == Gst.PadDirection.SINK else "UNKNOWN"
            caps = t.get_caps()
            structure =  caps.get_structure(0) if  caps.get_size() > 0 else None
            if structure :
                pairs = {}
                #print(structure.to_string())
                for i in range(structure.n_fields()):
                    name = structure.nth_field_name(i)
                    val =  structure.get_value(name)
                    pairs[name] = val
                capstemplates.append(Caps_template(padname,direction,pairs))

        return capstemplates

    def get_properties(self):
        return self.params

    def set_property(self,name,value):
        assert(self.gst_element and name in self.params)
        self.gst_element.set_property(name,value)
        if self.gst_element.get_property(name) == value :
            self.params[name] = value
            return True
        return False

    def set_property_dict(self,name,value,dictval):
        assert(self.gst_element and name in self.params)
        self.gst_element.set_property(name,value)
        if self.gst_element.get_property(name) == value :
            return True
        return False

    def get_clock(self):
        return self.gst_element.get_clock()

    def add_probe_on_pad(self,pad_name,event_name,func,data=None):
        assert(self.gst_element)
        self.name = self.params["name"]
        print(f"add probe pad_name : {pad_name}")
        if not data:
            data = {"pipeline":self.pipeline,"element":(self.id,pad_name)}

        return self.gst_element.get_static_pad(pad_name).add_probe(event_name,func,data)

    def p_buffer_pad_handler(self,pad,info,user_data=None):
        if user_data:
            buff = info.get_buffer()
            metrics = user_data
            clock = self.get_clock()
            if clock:
                time = clock.get_time()
                if time != None:
                    for m in metrics:
                        if pad.get_direction() == Gst.PadDirection.SRC:
                            if m.push_buffer_id(id(buff),time) :
                                m.push_data_src(time)
                        if pad.get_direction() == Gst.PadDirection.SINK:
                            if m.prev_src_data :
                                time = m.pop_buffer_id(id(buff),time)
                                if time :
                                    m.push_data_sink(time)
                            else :
                                m.push_data_sink(time)

        return Gst.PadProbeReturn.OK

pe = Processing_element

class Pipeline:
    def __init__(self,p = [],name = None):
        self.p = []
        for se in p:
            self.add(se)

        self.gui_visible = True
        self.gui_expanded = False
        self.gui_name = name
        self.state = 'stopped'
        self.clock = None
        self.latency = None

    def get_all_pads(self):
        pads = []
        for p in self.p:
            pads.append({p.name+"_sinks":p.sinks,p.name+'_srcs':p.srcs})
        return pads

    def add(self,element):
        name = element.id + f"_{len(self.p)}"
        element.params["name"] = name
        element.pipeline = self
        element.set_name(name)
        self.p.append(element)

    def connect(self,element_name,callback_name,func):
        gst_element = self.get_element_by_name(element_name)
        gst_element.connect(message_name,func)

    def start(self):
        assert(self.gst_pipeline)
        self.state = 'started'
        print(self.state)
        self.gst_pipeline.set_state(Gst.State.PLAYING)

    def stop(self):
        assert(self.gst_pipeline)
        self.state = 'stopped'
        print(self.state)
        self.gst_pipeline.set_state(Gst.State.NULL)

    def get_start_time(self):
        assert(self.gst_pipeline)
        return self.gst_pipeline.get_start_time()

    def set_start_time(self,time):
        assert(self.gst_pipeline)
        self.gst_pipeline.set_start_time(time)

    def time(self):
        assert(self.gst_pipeline)
        if self.clock == None:
            self.clock = self.gst_pipeline.get_clock()
            if not self.clock:
                return 0
        return self.clock.get_time()

    def init_gst_pipeline(self,on_bus_message):
        state = 0;
        gst_text = self.convert_to_launch()
        print(gst_text)
        self.gst_pipeline = Gst.parse_launch(gst_text)
        if self.gst_pipeline:
            self.bus = self.gst_pipeline.get_bus()
            state+=1 # gst_pipeline on
            self.clock = self.gst_pipeline.get_clock()
            if self.bus:
                self.bus.add_signal_watch()
                self.bus.connect('message', on_bus_message)
                state+=1 # bus on
            for e in self.p:
                e.gst_element = self.gst_pipeline.get_by_name(e.params["name"])
                e.props = dict([(p.name,e.gst_element.get_property(p.name)) for p in e.gst_element.list_properties()])
                e.sinks = e.gst_element.sinkpads
                e.srcs = e.gst_element.srcpads

        return self,state

    def get_element_by_name(self,name):
        for e in self.p:
            if "name" in e.params:
                if e.params["name"] == name :
                    return e
        return None

    def get_element_by_index(self,index):
        assert(index > -1  and index < len(self.p))
        return self.p[index]

    def on_bus_message(self,bus, message):
        self.latency = self.gst_pipeline.get_latency()
        message: Gst.Message
        t = message.type
        if t == Gst.MessageType.TAG:
            tags = message.parse_tag()
            print(tags.to_string())
        elif t == Gst.MessageType.EOS:
            print("EOS")
        elif t == Gst.MessageType.WARNING:
            err, debug = message.parse_warning()
            print('Warning: %s: %s\n' % (err, debug))
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print('Error: %s: %s\n' % (err, debug))

        return True

    def convert_from_launch(self,gst_text):

        def process(gste,pipeline):
            props = dict([(p.name,[gste.get_property(p.name),p]) for p in gste.list_properties()])
            elem_name = str(type(gste)).split('\'')[1].split('.')[1].lower()
            to_delete = set()
            for key,value in props.items():
                print(key,type(value[0]),value[1].flags & GObject.ParamFlags.WRITABLE)
                if not (value[1].flags & GObject.ParamFlags.WRITABLE):
                    props[key] = (type(value[0]),str(value[0]))
                    #to_delete.add(key)
                elif type(value[0]) in (bool,float,str):
                    props[key] = value[0]
                elif type(value[0]) == int:
                    props[key] = float(value[0])
                elif type(value[0]) == Gst.Caps:
                    props[key] = value[0]
                elif type(value[0]) != Gst.Pipeline:
                    try:
                        #print(type(value[0]))
                        nvalue = {}
                        for k,v in value[0].__enum_values__.items():
                            nvalue[v.value_nick] = k
                            #print(k,v.value_name)
                        props[key] = nvalue

                        print(value[0].value_name)
                        print(value[0].real)
                    except:
                        pass
                else :
                    to_delete.add(key)

                #print(key,value)
            id = props['name'] if 'name' in props else f'{elem_name}_{len(self.p)}'
            gste.set_name(id)

            for d in to_delete:
                print('deleting: ',d,props.pop(d,None))

            sinks = gste.sinkpads
            srcs = gste.srcpads
            p_element = pe(id=id,pipeline=pipeline,gst_element=gste,params = props,srcs = srcs, sinks = sinks)
            for snk in sinks:
               snk.add_probe(Gst.PadProbeType.BUFFER,p_element.p_buffer_pad_handler,p_element.metrics)
            for src in srcs:
               src.add_probe(Gst.PadProbeType.BUFFER,p_element.p_buffer_pad_handler,p_element.metrics)

            self.p.append(p_element)

        self.gst_pipeline = Gst.parse_launch(gst_text)
        if self.gst_pipeline:
            self.bus = self.gst_pipeline.get_bus()
            if self.bus:
                self.bus.add_signal_watch()
                self.bus.connect('message', self.on_bus_message)
                print(self.bus.poll(Gst.MessageType.EOS | Gst.MessageType.ERROR,0))
            self.gst_pipeline.iterate_elements().foreach(process,self)
        elif error:
            raise Exception('Some thing wrong with the pipeline',error)

        return self

    def convert_to_launch(self):
        ss = []
        for e in self.p:
            sp = []
            sp.append(e.id)
            if e.params:
                for k,v in e.params.items():
                    if v:
                        sp.append(f'{k}={v}')
                    else:
                        sp.append(f'{k}')
            ss.append(' '.join(sp))

        return ' ! '.join(ss)


#g_host = '127.0.0.1'
g_host = '239.3.0.1'
g_video_port = '6000'
g_audio_port = '5002'

def fake_pipeline():
    return Pipeline([pe('appsrc'),
                    pe('fakesink')])

def video_source_pipeline():

    return Pipeline([pe('videotestsrc'),
                    pe('capsfilter',{'caps':'\"video/x-raw, width=640, height=480, format=I420, framerate=60/1\"'}),
                    pe('timeoverlay'),
#                   pe('autovideosink')])
                    pe('queue'),
                    pe('x264enc', {"tune":"zerolatency"}),
                    pe('h264parse'),
                    pe('rtph264pay'),#{ "config-interval":-1}),
                    pe('udpsink',{'host':g_host,'port':g_video_port})])

def video_cam_pipeline():
    return Pipeline([pe('v4l2src',{'device':'/dev/video0'}),
                        pe('capsfilter',{'caps':'\"video/x-raw, format=RGB\"'}),
                        #pe('autovideosink')])
                        pe('xvimagesink')])
def video_cam_src():
    return Pipeline([pe('v4l2src',{'device':'/dev/video0'}),
                        pe('capsfilter',{'caps':'\"image/jpeg, format=RGB\"'}),
                        pe('jpegdec'),
                        pe('x264enc',{'tune':'zerolatency'}),
                        pe('h264parse'),
                        pe('rtph264pay',{ "config-interval":-1}),
                        pe('udpsink',{'host':g_host,'port':g_video_port})])

def video_sink_pipeline():
    h264_pipeline =[pe('udpsrc',{'uri':f'udp://{g_host}:{g_video_port}'}),
                    pe('capsfilter',{'caps':'\"application/x-rtp, encoding-name=H264\"'}),
                    pe('rtph264depay'),
                    pe('h264parse'),
                    pe('avdec_h264'),
                    pe('queue'),#{"max_size-buffers":1}),
                    pe('identity'),#,{'dump':'true'}),
                    #pe('appsink',{'emit-signals':'true'})]
                    #pe('queue'),
                    pe('autovideosink')]
    return Pipeline(h264_pipeline)

def audio_source_pipeline():

    return Pipeline([#pe('audiotestsrc',{"apply-tick-ramp":'true',"wave":"8","volume":"0.2","sine-periods-per-tick":'100',"marker-tick-period":'3'}),
                     pe('autoaudiosrc'),
                     pe('queue'),
                     pe('opusenc'),
                     pe('rtpopuspay'),
                     pe('capsfilter',{'caps':'\"application/x-rtp, encoding-name=OPUS, clock-rate=48000, payload=97\"'}),
                     pe('udpsink',{'host':g_host,'port':g_audio_port,'-v':''})])

def audio_sink_pipeline():

    return Pipeline([pe('udpsrc',{'uri':f'udp://{g_host}:{g_audio_port}'}),
                    pe('capsfilter',{'caps':'\"application/x-rtp, encoding-name=OPUS, clock-rate=48000, payload=97\"'}),
                    pe('rtpjitterbuffer'),
                    pe('rtpopusdepay'),
                    pe('queue'),
                    pe('opusdec'),
                    pe('audioconvert'),
                    #pe('capsfilter',{'caps':'\"audio/x-raw\"'}),
                    pe('autoaudiosink')])


def print_message(bus, message):
    message: Gst.Message
    t = message.type
    if t == Gst.MessageType.TAG:
        tags = message.parse_tag()
        #print(tags.to_string())
    elif t == Gst.MessageType.EOS:
        print("EOS")
    elif t == Gst.MessageType.WARNING:
        err, debug = message.parse_warning()
        print('Warning: %s: %s\n' % (err, debug))
    elif t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        print('Error: %s: %s\n' % (err, debug))

    return True

#note(lev) : add decorator to not reeturn the gst pad Probe OK explicitly
def probe_down_func(pad,info,user_data=None):
    event = info.get_event()
    if event.type == Gst.EventType.EOS:
        print("down")
    return Gst.PadProbeReturn.OK

def probe_up_func(pad,info,user_data=None):
    print("up")
    return Gst.PadProbeReturn.OK

queue_size = 60
queue = [None]*queue_size
queue_top = 0


def take_off(sink,data = None):
    global queue,queue_top,queue_size
    sample = sink.emit('pull-sample')
    queue[queue_top] = sample
    queue_top = (queue_top + 1 ) % queue_size
    return Gst.FlowReturn.OK

class ElementTiming:
    def __init__(self,name):
        self.src_time = []
        self.sink_time = []
        self.element_name = None

element_timings = {}
etLock = threading.RLock()

def print_pad_sink(pad,info,data = None):
    if data and "pipeline" in data:
        time = data['pipeline'].time()
#        print(f"data element:{data['element']} time: {time}")
        element_name = data['element'][0]
        element_pad  = data['element'][1]
        push_time_to = None
        with etLock:
            if element_name not in element_timings :
                element_timings[element_name] = ElementTiming(element_name)

            print(element_name,element_pad)
            if element_pad == 'src':
                element_timings[element_name].src_time.append(time)
            if element_pad == 'sink':
                element_timings[element_name].sink_time.append(time)

    return Gst.PadProbeReturn.OK

def print_pad_src(pad,info,data = None):
    if data and "pipeline" in data:
        time = data['pipeline'].time()
#        print(f"data element:{data['element']} time: {time}")
        element_name = data['element'][0]
        element_pad  = data['element'][1]
        push_time_to = None
        with etLock:
            if element_name not in element_timings :
                element_timings[element_name] = ElementTiming(element_name)

            print(element_name,element_pad)
            if element_pad == 'src':
                element_timings[element_name].src_time.append(time)
            if element_pad == 'sink':
                element_timings[element_name].sink_time.append(time)

    return Gst.PadProbeReturn.OK

t = threading.Thread(target = loop,daemon = True)
t.start()

from sys import argv
if len(argv) > 1 and argv[1] == 'videosink':
    print(video_sink_pipeline().convert_to_launch())
if len(argv) > 1 and argv[1] == 'videosrc':
    print(video_source_pipeline().convert_to_launch())
if len(argv) > 1 and argv[1] == 'audiosink':
    print(audio_sink_pipeline().convert_to_launch())
if len(argv) > 1 and argv[1] == 'audiosrc':
    print(audio_source_pipeline().convert_to_launch())
if len(argv) > 1 and argv[1] == 'videocam_start':
    pipe,state = video_cam_src().init_gst_pipeline(print_message)
    pipe.start()
    input()
    pipe.stop()


if len(argv) > 1 and argv[1] == 'launch_test':
    launch_test = "videotestsrc ! autovideosink"
    pipeline = Pipeline()
    pipeline.convert_from_launch(launch_test)
    pipeline.start()

    input()
    pipeline.stop()

if len(argv) > 1 and argv[1] == 'fake_pipeline':
    pipe,state = fake_pipeline().init_gst_pipeline(print_message)
    print(pipe.get_element_by_index(0).get_properties())
    pipe_pads = pipe.get_all_pads()
    item = None

    def process(gste):
        props = dict([(p.name,gste.get_property(p.name)) for p in gste.list_properties()])

    pipe.gst_pipeline.iterate_elements().foreach(process)

    #for pd in pipe_pads:
    #    for k,v in pd.items():
    #        print(k)
    #        for gsp in v:
    #            print(dir(gsp))
    #    #for ppv in pv:


if len(argv) > 1 and argv[1] == 'videosink_start':
    videosink_pipe,state = video_sink_pipeline().init_gst_pipeline(print_message)
    videosink_pipe.start()
    videosink_pipe.get_element_by_index(0).add_probe_on_pad('src',Gst.PadProbeType.BUFFER,print_pad_src)
    videosink_pipe.get_element_by_index(1).add_probe_on_pad('sink',Gst.PadProbeType.BUFFER,print_pad_src)
    videosink_pipe.get_element_by_index(1).add_probe_on_pad('src',Gst.PadProbeType.BUFFER,print_pad_src)
    videosink_pipe.get_element_by_index(2).add_probe_on_pad('sink',Gst.PadProbeType.BUFFER,print_pad_src)
    videosink_pipe.get_eement_by_index(2).add_probe_on_pad('src',Gst.PadProbeType.BUFFER,print_pad_src)
    videosink_pipe.get_element_by_index(3).add_probe_on_pad('sink',Gst.PadProbeType.BUFFER,print_pad_src)
    videosink_pipe.get_element_by_index(3).add_probe_on_pad('src',Gst.PadProbeType.BUFFER,print_pad_src)
    videosink_pipe.get_element_by_index(4).add_probe_on_pad('sink',Gst.PadProbeType.BUFFER,print_pad_src)
    videosink_pipe.get_element_by_index(4).add_probe_on_pad('src',Gst.PadProbeType.BUFFER,print_pad_src)
    videosink_pipe.get_element_by_index(5).add_probe_on_pad('sink',Gst.PadProbeType.BUFFER,print_pad_src)
    videosink_pipe.get_element_by_index(5).add_probe_on_pad('src',Gst.PadProbeType.BUFFER,print_pad_src)
    videosink_pipe.get_element_by_index(6).add_probe_on_pad('sink',Gst.PadProbeType.BUFFER,print_pad_src)
    element_6 = videosink_pipe.get_element_by_index(6)
    print(dir(element_6.gst_element))
    print(element_6.get_property("sync"))
    element_6.set_property('sync',True)
    print(element_6.get_property("sync"))
    print('sinks:',element_6.sinks)
    print('srcs',element_6.srcs)
    e6_props = element_6.gst_element.list_properties()
    print(e6_props)
    for p in e6_props:
        print(p.name,p.default_value)
        print(p.flags)
    #videosink_pipe.get_j
    #videosink_pipe.get_element_by_index(0).add_probe_on_pad('src',Gst.PadProbeType.EVENT_DOWNSTREAM,probe_down_func)
    #videosink_pipe.get_element_by_index(1).add_probe_on_pad('sink',Gst.PadProbeType.BUFFER,print_pad)
    #videosink_pipe.get_element_by_index(1).add_probe_on_pad('sink',Gst.PadProbeType.BUFFER,print_pad)
    #videosink_pipe.get_element_by_name('appsink_6').connect("new-sample",take_off)
    input("Press any key\n")
    videosink_pipe.stop()
    start_time = 0
    end_time = 0
    for k,v  in element_timings.items():
        v.sink_time.sort()
        v.src_time.sort()
    for k,v  in element_timings.items():
        if start_time == None and not v.sink_time:
            start_time = min(v.src_time)
        if not v.src_time and v.sink_time:
            if end_time == None:
                end_time = min(v.sink_time)
            continue
        src_time = np.array(v.src_time)
        sink_time = np.array(v.sink_time)
        if src_time.shape != sink_time.shape:
            continue
        delta = src_time - sink_time
        print(f"{k} {np.average(delta)/1000000}")
    print(start_time,end_time,((end_time - start_time)/1e6))
            #print(f"{k} {v.sink_time}")
if len(argv) > 1 and argv[1] == 'videosrc_start':
    videosrc_pipe,state = video_source_pipeline().init_gst_pipeline(print_message)
    videosrc_pipe.start()
    input("Press any key")
    videosrc_pipe.stop()

