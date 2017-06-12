import os
import re
import sys
import cffi

from ._native import lib, ffi


_directive_re = re.compile(r'^\s*#.*?$(?m)')
lib.cbindgen_init()


def rustcall(func, *args):
    err = ffi.new('BindgenError *')
    try:
        rv = func(*(args + (err,)))
        if err.failed:
            raise RuntimeError(ffi.string(err.msg).decode('utf-8'))
        return rv
    finally:
        if err.failed:
            lib.cbindgen_clear_err(err)


def generate_header(crate_path):
    rv = rustcall(lib.cbindgen_generate_headers, crate_path)
    header = ffi.string(rv)
    try:
        if sys.version_info >= (3, 0):
            header = header.decode('utf-8')
        return header
    finally:
        lib.cbindgen_free_string(rv)


def make_ffi(module_path, crate_path, cached_header_filename):
    if os.path.isfile(cached_header_filename):
        with open(cached_header_filename, 'rb') as f:
            header = f.read()
    else:
        header = generate_header(crate_path)
    header = _directive_re.sub('', header)
    ffi = cffi.FFI()
    ffi.cdef(header)
    ffi.set_source(module_path, None)
    return ffi
