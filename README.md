# Pipeline inspector

GSTREAMER pipeline inspector lets you see pipeline element and see how well they perform 

useful for viewing latency for plugins in a pipeline

![Screenshot from 2022-04-24 03-47-26](https://user-images.githubusercontent.com/7438866/164950979-62d6cd0e-4c5a-4f43-b6f2-49010bc39648.png)


### Installation (ubuntu 20.04)

```
sudo apt-get install git autoconf automake libtool
sudo apt-get install gstreamer-1.0
sudo apt-get install gstreamer1.0-dev
sudo apt-get install python3-gi python-gst-1.0 
sudo apt-get install libgirepository1.0-dev
sudo apt-get install libcairo2-dev gir1.2-gstreamer-1.0

pip install pycairo
pip install PyGObject

pip install imgui[glfw]
```


### Run 
```
python3 inspector.py 
```
