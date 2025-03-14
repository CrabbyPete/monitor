gst-launch-1.0 libcamerasrc   ! \
 video/x-raw,width=640,height=480,framerate=30/1,format=I420   ! \
 videoconvert   ! \
 x264enc speed-preset=ultrafast tune=zerolatency byte-stream=true key-int-max=75   ! \
 video/x-h264,level='(string)4'   ! \
 h264parse   ! \
 video/x-h264,stream-format=avc,alignment=au,width=640,height=480,framerate=30/1   ! \
 kvssink stream-name="VideoPi"