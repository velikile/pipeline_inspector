import imgui
import glfw
import time
from imgui.integrations.glfw import GlfwRenderer
import OpenGL.GL as gl
from math import sin
from array import array
seconds_per_frame = 1/60
loop_window_width = 1000
from simple_recorder import Pipeline
import numpy as np
from gi.repository import Gst

g_graph_size = 400

def main():

    if not glfw.init():
        return
    # Create a windowed mode window and its OpenGL context
    window = glfw.create_window(1920, 1080, "Pipeline_introspector", None, None)
    #print(dir(imgui))
    if not window:
        glfw.terminate()
        return

    # Make the window's context current
    glfw.make_context_current(window)

    imgui.create_context()
    imgui.get_io().display_size = 100, 100
    imgui.get_io().fonts.get_tex_data_as_rgba32()

    renderer = GlfwRenderer(window)

    gl.glClearColor(1, 1, 1, 1)
    gl.glDisable(gl.GL_DEPTH_TEST)
    # Loop until the user closes the window
    cycle_counter = 0
    frametimes = [[x,0] for x in range(g_graph_size)]
    fps= [[x,0] for x in range(g_graph_size)]
    pipelines = []
    frame_time = 0
    p = Pipeline([],'video_pipe')
    #p.convert_from_launch('videotestsrc ! capsfilter caps=video/x-raw ! queue ! x264enc ! avdec_h264 ! autovideosink')
    p.convert_from_launch("videotestsrc ! capsfilter caps=\"video/x-raw,format=GRAY8 ,width=640,height=480,framerate=100/1\"! timeoverlay ! queue ! videoconvert ! autovideosink")
    pipelines.append(p)
    p1 = Pipeline([],'audio_pipe')
    p1.convert_from_launch("audiotestsrc volume=0.1 ! autoaudiosink")
    pipelines.append(p1)
    p2 = Pipeline([],'rtp source')
    p2.convert_from_launch("videotestsrc pattern=ball ! capsfilter caps=\"video/x-raw, width=640, height=480\" ! x264enc tune=zerolatency ! h264parse ! rtph264pay config-interval=-1 ! udpsink host=239.3.0.1 port=5001")
    pipelines.append(p2)
    p3 = Pipeline([],'video_pipe1')
    #p3.convert_from_launch("udpsrc port=5001 ! rtph264depay ! avdec_h264 ! queue ! videoconvert ! autovideosink")
    p3.convert_from_launch("udpsrc port=5001 ! capsfilter ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! autovideosink")
    pipelines.append(p3)
    p4 = Pipeline([],'video_pipe_crop')
    p4.convert_from_launch("udpsrc port=5001 ! capsfilter ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! videocrop ! autovideosink")
    pipelines.append(p4)

    glfw.set_time(0)
    while not glfw.window_should_close(window):
        glfw.poll_events()
        renderer.process_inputs()

        start = glfw.get_time()

        imgui.new_frame()

        #plot_values = array('f',[x for x in frametimes])
        ## open new window context
        imgui.begin("pipeline selection", True)
        metered_elements = []
        for p in pipelines:
            if p.state == 'stopped':
                imgui.push_style_color(imgui.COLOR_HEADER, 1.0, 0.0, 0.0)
            elif p.state == 'started':
                imgui.push_style_color(imgui.COLOR_HEADER, 0.0, 1.0, 0.0)
            p.gui_expanded, p.gui_visible = imgui.collapsing_header(p.gui_name, p.gui_visible)
            imgui.pop_style_color()
            imgui.push_id(str(p))
            imgui.same_line(spacing=50)
            if imgui.button("start_pipeline"):
                if p == pipelines[3]:
                    print('setting_clock')
                    print(pipelines[0].get_start_time())
                    print(p.get_start_time())
                    p.set_start_time(pipelines[0].get_start_time())
                    print(p.get_start_time())
                p.start()
                print(p.get_start_time())
            imgui.same_line(spacing=10)
            if imgui.button("stop_pipeline"):
                p.stop()
            imgui.pop_id()

            if p.gui_expanded:
                imgui.indent()
                for e in p.p:
                    imgui.push_style_color(imgui.COLOR_HEADER, 1.0, 1.0, 0.0)
                    imgui.push_style_color(imgui.COLOR_TEXT, 0.0, 0.0, 0.0)
                    e.gui_expanded, e.gui_visible = imgui.collapsing_header(e.id, e.gui_visible)
                    imgui.pop_style_color(2)
                    if(e.gui_expanded):
                        imgui.indent()
                        templates = e.get_caps_templates()
                        for t in templates:
                            imgui.push_style_color(imgui.COLOR_TEXT, 1.0,1.0, 1.0)
                            imgui.push_style_color(imgui.COLOR_HEADER, 0.0, 0.0, 0.0)
                            imgui.push_id(str(id(e)))
                            t.gui_expanded, t.gui_visible = imgui.collapsing_header(f"{t.padname} -> {t.direction}", e.gui_visible)
                            if t.gui_expanded:
                                imgui.push_text_wrap_position(500)
                                for k,v in t.kvpairs.items():
                                    imgui.text(f"{k}:{v}")
                                imgui.pop_text_wrap_pos()
                            imgui.pop_style_color(2)
                            imgui.pop_id()
                        eprops = e.get_properties()
                        for key,val in eprops.items():
                            imgui.push_style_color(imgui.COLOR_TEXT, 0.0, 1.0, 0.0)
                            #imgui.text(f'{key}:{val[0]}')
                            if type(val) == Gst.Caps :
                                strval = val.to_string()
                                changed,strval = imgui.input_text(key,strval,400)
                                if changed :
                                    newCaps = Gst.caps_from_string(strval)
                                    if newCaps :
                                        e.set_property(key,newCaps)
                                    else:
                                        e.set_property(key,val)
                            elif type(val) == float :
                                changed,val = imgui.input_float(key,val)
                                if changed :
                                    e.set_property(key,val)
                            elif type(val) == int :
                                try:
                                    changed,val = imgui.input_float(key,val)
                                    if changed and val.is_integer() :
                                        e.set_property(key,int(val))
                                except :
                                    pass

                            elif type(val) == bool :
                                clicked = imgui.radio_button(key,val)
                                if clicked :
                                    val = not val
                                    e.set_property(key,val)
                            elif type(val) == dict :
                                dictkeys = list(val)
                                clicked,val['selected'] = imgui.combo(key,val.get('selected',val[dictkeys[0]]),list(val))
                                if clicked :
                                    e.set_property_dict(key,val['selected'],val)
                            elif type(val) == list :
                                imgui.text(','.join(str(val)))

                            imgui.pop_style_color()

                        imgui.unindent()

                        imgui.indent()
                        for metric in e.metrics:
                            imgui.push_id(str(metric))
                            imgui.push_style_color(imgui.COLOR_TEXT, 1.0, 1.0, 0.0)
                            _,metric.gui_checked = imgui.checkbox(metric.gui_name,metric.gui_checked)
                            if metric.gui_checked:
                                metered_elements.append((metric,e))
                            imgui.pop_style_color()
                            imgui.pop_id()
                        imgui.unindent()
                imgui.unindent()

        # draw text label inside of current window
        #imgui.text("Hello world!")

        ## close current window context
        imgui.end()

        imgui.begin("graphs", True)

        # draw text label inside of current window
        if frame_time > 0:
            imgui.push_style_color(imgui.COLOR_TEXT, 1.0, 0.0, 0.0)
            imgui.text(f"frame_time :{frame_time}")
            imgui.push_style_color(imgui.COLOR_TEXT, 1.0, 0.0, 1.0)
            imgui.text(f"fps: {1000/frame_time}")
            imgui.pop_style_color(2)

        graph_w= 1000
        graph_h = 250
        drawlist = imgui.get_window_draw_list()
        xoff,yoff = imgui.get_cursor_screen_pos()
        fps_draw = [(x%graph_w+xoff,y+yoff) for x,y in fps]
        frametimedraw = [(x%graph_w+xoff,y+yoff) for x,y in frametimes]
        drawlist.add_polyline(fps_draw,imgui.get_color_u32_rgba(1,0,0,1), closed=False, thickness=1)
        drawlist.add_polyline(frametimedraw,imgui.get_color_u32_rgba(1,0,1,1), closed=False, thickness=1)
        imgui.set_cursor_screen_pos((xoff,yoff + graph_h))

        imgui.columns(2, "locations")
        xwin,ywin = imgui.get_window_position()
        for me,e in metered_elements:
            if me.name == 'Latency':
                xoff,yoff = imgui.get_cursor_screen_pos()
                if me.prev_src_data and me.prev_sink_data:
                    diff = np.array(me.sink_data)[:,0] - np.array(me.src_data)[:,0]
                    def clamp_to_zero(x):
                        return x if x >0 else 0
                    func = np.vectorize(clamp_to_zero)
                    diff = func(diff)

                    mftime = [(i+ xoff ,graph_h + yoff + d/1e6) for i,d in enumerate(diff)]
                    tpos = imgui.get_cursor_screen_pos()
                    imgui.set_cursor_screen_pos((xoff,graph_h + yoff - 50))
                    imgui.text(f"{e.id} latency:{np.average(diff/1e6)}")
                    drawlist.add_polyline(mftime,imgui.get_color_u32_rgba(1,1,0,1), closed=False, thickness=1)
                    imgui.set_cursor_screen_pos(tpos)
            elif me.name == 'Clock':
                xoff,yoff = imgui.get_cursor_screen_pos()
                clock = e.get_clock()
                if clock:
                    etime = clock.get_time()
                    imgui.push_style_color(imgui.COLOR_TEXT, 1.0, 0.0, 1.0)
                    imgui.text(f"{e.id} : clock_time :{etime}")
                    imgui.pop_style_color()
            elif me.name == 'FrameTime':
                xoff,yoff = imgui.get_cursor_screen_pos()
                if me.prev_src_data :
                    imgui.next_column()
                    xoff = imgui.get_column_offset()
                    mftime = [(x + xoff + xwin  ,yoff + (graph_h/2-y/1e6)) for x,(t,y) in enumerate(me.src_data)]
                    avg = np.average(mftime)
                    imgui.text(f"{e.id},src,avgrage time:{avg}")
                    drawlist.add_polyline(mftime,imgui.get_color_u32_rgba(0,1,1,1), closed=False, thickness=1)
                    base = [(xoff + xwin ,yoff + graph_h/2),(xoff + xwin + g_graph_size ,yoff + graph_h/2)]
                    drawlist.add_polyline(base,imgui.get_color_u32_rgba(.5,.5,.5,1), closed=False, thickness=1)
                if me.prev_sink_data:
                    imgui.next_column()
                    xoff = imgui.get_column_offset()
                    mftime = [(x + xoff + xwin ,yoff+graph_h/2 - y/1e6) for x,(t,y) in enumerate(me.sink_data)]
                    avg = np.average(mftime)
                    #imgui.set_cursor_screen_pos((xoff+g_graph_size,yoff))
                    imgui.text(f"{e.id},sink,avgrage time:{avg}")
                    drawlist.add_polyline(mftime,imgui.get_color_u32_rgba(0,1,0,1), closed=False, thickness=1)
                    base = [(xoff + xwin,yoff + graph_h/2),(xoff + xwin + g_graph_size ,yoff + graph_h/2)]
                    drawlist.add_polyline(base,imgui.get_color_u32_rgba(1,1,1,1), closed=False, thickness=1)

        imgui.columns()

        ## close current window context
        imgui.end()

        ## pass all drawing comands to the rendering pipeline
        ## and close frame context
        imgui.render()
        imgui.end_frame()
        renderer.render(imgui.get_draw_data())
        end = glfw.get_time()
        frame_time = (end-start)*1e4
        cycle_counter+=1
        if frame_time < (seconds_per_frame * 1000) :
            time.sleep(seconds_per_frame)
        else:
            time.sleep(0)




        frameindex = cycle_counter % len(frametimes)
        frametimes[frameindex][1] = frame_time
        fps[frameindex][1] = 1000/frame_time
        # Swap front and back buffers
        glfw.swap_buffers(window)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)

        # Poll for and process events

    renderer.shutdown()
    glfw.terminate()

if __name__ == "__main__":
    main()
