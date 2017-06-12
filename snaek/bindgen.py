import os
import sys

from ._bindgen import lib, ffi


lib.bindgen_init()


def rustcall(func, *args):
    err = ffi.new('BindgenError *')
    try:
        rv = func(*(args + (err,)))
        if err.failed:
            raise RuntimeError(ffi.string(err.msg).decode('utf-8'))
        return rv
    finally:
        if err.failed:
            lib.bindgen_clear_err(err)


def generate_header(crate_path):
    rv = rustcall(lib.bindgen_generate_headers, crate_path)
    header = ffi.string(rv)
    try:
        if sys.version_info >= (3, 0):
            header = header.decode('utf-8')
        return header
    finally:
        lib.bindgen_free_string(rv)
