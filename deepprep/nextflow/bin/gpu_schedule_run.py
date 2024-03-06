#! /usr/bin/env python3
import os
import sys
import subprocess
import redis_lock
from redis_lock import StrictRedis

from gpu_manage import GPUManager, check_gpus


if __name__ == '__main__':
    if sys.argv[1].isdigit():
        gpu = sys.argv[1]
    elif sys.argv[1].lower() == 'cpu':
        gpu = ''
    else:
        print(f'Auto select GPU by ： {sys.argv[1]}')
        gpu_manager = GPUManager()
        gpu = gpu_manager.auto_choice()

    os.environ['CUDA_VISIBLE_DEVICES'] = gpu
    print(f'INFO: GPU: {gpu}')
    print(f'INFO: sys.argv : {sys.argv}')
    if gpu:
        gpu_available, info = check_gpus(11.8, 11000)
        if not gpu_available:
            raise ImportError(info)
    assert os.path.exists(sys.argv[4]), f"{sys.argv[4]}"
    if sys.argv[3].lower() == 'local':
        conn = StrictRedis()
        if sys.argv[2] == 'double':
            with redis_lock.Lock(conn, 'nextflow-local-gpu-1'), redis_lock.Lock(conn, 'nextflow-local-gpu-2'):
                cmd = f"python3 " + " ".join(sys.argv[4:])
                print(f'INFO: GPU: {cmd}')
                status, results = subprocess.getstatusoutput(cmd)
                print(results)
                assert status == 0
        else:
            if 'lh' in sys.argv:
                lock_name = 'nextflow-local-gpu-1'
            elif 'rh' in sys.argv:
                lock_name = 'nextflow-local-gpu-2'
            else:
                lock_i = int(conn.lpop('lock_index'))
                lock_name = ['nextflow-local-gpu-1', 'nextflow-local-gpu-2'][lock_i]
            print(f"lock_name: {lock_name}")
            with redis_lock.Lock(conn, lock_name):
                cmd = f"python3 " + " ".join(sys.argv[4:])
                print(f'INFO: GPU: {cmd}')
                status, results = subprocess.getstatusoutput(cmd)
                print(results)
                assert status == 0
    else:
        cmd = f"python3 " + " ".join(sys.argv[4:])
        print(f'INFO: GPU: {cmd}')
        status, results = subprocess.getstatusoutput(cmd)
        print(results)
        assert status == 0
