.. include:: links.rst

============
Installation
============

Run with Docker (step-by-step)
---------------------------------

DeepPrep provides a Docker image as the recommended way to get started.

.. warning::
    **Required Environment**
        + Ubuntu:  >= 20.04
        + RAM: >= 16GB
        + Swap space: >=16G
        + Disk: >= 20G
        + Graphics Driver VRAM: >= 12GB (optional GPU device)
        + NVIDIA Driver Version: >= 520.61.05 (optional GPU device)
        + CUDA Version: >= 11.8 (optional GPU device)

1. Install Docker if you don't have one (`Docker Installation Page`_).


2. Test Docker with the ``hello-world`` image::

    $ docker run -it --rm hello-world

The following message should appear:

::

    Hello from Docker!
    This message shows that your installation appears to be working correctly.

    To generate this message, Docker took the following steps:
     1. The Docker client contacted the Docker daemon.
     2. The Docker daemon pulled the "hello-world" image from the Docker Hub.
        (amd64)
     3. The Docker daemon created a new container from that image which runs the
        executable that produces the output you are currently reading.
     4. The Docker daemon streamed that output to the Docker client, which sent it
        to your terminal.

    To try something more ambitious, you can run an Ubuntu container with:
     $ docker run -it ubuntu bash

    Share images, automate workflows, and more with a free Docker ID:
     https://hub.docker.com/

    For more examples and ideas, visit:
     https://docs.docker.com/get-started/

3. If you have GPUs on your host machine, you can check whether the GPUs are accessible by adding the flag ``--gpus all``::

    $ docker run -it --rm --gpus all hello-world

The same output as before is expected. If an error message pops up (something like below), please double-check that the Docker was installed properly.

.. code-block:: none

    docker: Error response from daemon: failed to create task for container: failed to create shim task: OCI runtime create failed: runc create failed: unable to start container process: error during container init: error running hook #0: error running hook: exit status 1, stdout: , stderr: Auto-detected mode as 'legacy'
    nvidia-container-cli: initialization error: load library failed: libnvidia-ml.so.1: cannot open shared object file: no such file or directory: unknown.


.. note::

    Without ``--gpus all``, the container will only have access to the CPU resources of the host machine.

4. Pull the Docker image::

    $ docker pull ninganme/deepprep:23.1.0

5. Run the Docker image ::

    $ docker run --rm ninganme/deepprep:23.1.0

If the Docker image was pulled successfully, you would see the following message:

.. code-block:: none

    INFO: args:
    DeepPrep args:
    deepprep-docker [bids_dir] [output_dir] [{participant}] [--bold_task_type TASK_LABEL]
                    [--fs_license_file PATH] [--participant-label PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]]
                    [--subjects_dir PATH] [--skip_bids_validation]
                    [--anat_only] [--bold_only] [--bold_sdc] [--bold_confounds]
                    [--bold_surface_spaces '[fsnative fsaverage fsaverage6 ...]']
                    [--bold_volume_space {MNI152NLin6Asym MNI152NLin2009cAsym}] [--bold_volume_res {02 03...}]
                    [--device { {auto 0 1 2...} cpu}]
                    [--cpus 10] [--memory 5]
                    [--ignore_error] [--resume]
