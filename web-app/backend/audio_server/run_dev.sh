docker run --gpus all --ipc=host -it --rm -v .:/usr/src/app -p 8888:8888 -p 6006:6006 --ulimit memlock=-1 --ulimit \
stack=67108864 --entrypoint /bin/bash audio