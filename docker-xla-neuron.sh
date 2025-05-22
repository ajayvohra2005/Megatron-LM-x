#!/bin/bash

docker run -t -d -v /home/ubuntu/efs/git/Megatron-LM-x:/megatron \
    -v /tmp:/tmp \
    -v /home/ubuntu/efs/data:/data -v /home/ubuntu/efs/datasets:/datasets \
    --shm-size=16g \
    --net=host \
    --device=/dev/neuron0 \
    --device=/dev/neuron1 \
    --device=/dev/neuron2 \
    --device=/dev/neuron3 \
    --device=/dev/neuron4 \
    --device=/dev/neuron5 \
    --device=/dev/neuron6 \
    --device=/dev/neuron7 \
    --device=/dev/neuron8 \
    --device=/dev/neuron9 \
    --device=/dev/neuron10 \
    --device=/dev/neuron11 \
    --device=/dev/neuron12 \
    --device=/dev/neuron13 \
    --device=/dev/neuron14 \
    --device=/dev/neuron15 docker.io/library/megatron-lm-x:latest  sleep infinity
