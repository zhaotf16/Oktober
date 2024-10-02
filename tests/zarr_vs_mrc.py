'''
Testing Zarr and MRC formats for cryoET data.

Date : 2024-10-02

Author : Tianfang Zhao
'''


from typing import Any, Optional
import time
import mrcfile.mrcmemmap
import mrcfile.mrcobject
import numpy as np
import zarr
import mrcfile


def exec_with_timeit(code : str, desc : Optional[str]) -> Any:
    '''
    Execute a code block and print time cost.
    '''
    if desc is None:
        desc = code
    exec_data = {}
    start = time.time()
    exec(f'ret = {code}', globals(), exec_data)
    print(f'{desc} cost {time.time()-start}')

    return exec_data["ret"]


def size_test(mrc : mrcfile.mrcobject,
              zarrfile : zarr.Array,
              mrcmap : mrcfile.mrcmemmap) -> None:
    '''
    Testing performance of getting size of tomogram.
    '''
    exec_with_timeit(f'mrc.data.shape', desc='Getting shape of MrcObject')
    exec_with_timeit(f'zarrfile[0].shape', desc='Getting shape of ZarrArray')
    exec_with_timeit(f'mrcmap.data.shape', desc='Getting shape of MrcMemmap')


def slice_index_test(mrc : mrcfile.mrcobject,
                     arrfile : zarr.Array,
                     mrcmap : mrcfile.mrcmemmap) -> None:
    '''
    Testing performance of slice_indexing of MRC and Zarr formats.
    '''
    exec_with_timeit(f'[np.sum(mrc.data[i]) for i in range(200)]', desc='Slice indexing of MrcObject')
    exec_with_timeit(f'[np.sum(zarrfile[0][i]) for i in range(200)]', desc='Slice indexing of ZarrFile')
    exec_with_timeit(f'[np.sum(mrcmap.data[i]) for i in range(200)]', desc='Slice indexing of MrcMemmap')


def block_index_test(mrc : mrcfile.mrcobject,
                     zarrfile : zarr.Array,
                     mrcmap : mrcfile.mrcmemmap) -> None:
    '''
    Testing performance of block indexing of MRC and Zarr formats.
    '''
    exec_with_timeit(f'[np.sum(mrc.data[i:i+50,i:i+300,i:i+300]) for i in range(150)]', desc='Block indexing of MrcObject')
    exec_with_timeit(f'[np.sum(zarrfile[0][i:i+50,i:i+300,i:i+300]) for i in range(150)]', desc='Block indexing of ZarrFile')
    exec_with_timeit(f'[np.sum(mrcmap.data[i:i+50,i:i+300,i:i+300]) for i in range(150)]', desc='Block indexing of MrcMemmap')


def element_index_test():
    '''
    Testing performance of element indexing of MRC and Zarr formats.
    '''

if __name__ == "__main__":

    mrc = exec_with_timeit('mrc = mrcfile.open("../test.mrc", mode="r")', desc='Opening test.mrc')
    zarrfile = exec_with_timeit('zar = zarr.load("../test.zarr")', desc='Opening test.zarr')
    mrcmap = exec_with_timeit('mrc_map = mrcfile.mmap("../test.mrc", mode="r")', desc='Opening test.mrc via MemoryMap')

    size_test(mrc, zarrfile, mrcmap)
    slice_index_test(mrc, zarrfile, mrcmap)
    block_index_test(mrc, zarrfile, mrcmap)
