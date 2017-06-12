import os
import re
import cffi


_directive_re = re.compile(r'^\s*#.*?$(?m)')


def make_ffi(module_path, crate_path, cached_header_filename=None):
    """Creates a FFI instance for the given configuration."""
    if cached_header_filename is not None and \
       os.path.isfile(cached_header_filename):
        with open(cached_header_filename, 'rb') as f:
            header = f.read()
    else:
        from .bindgen import generate_header
        header = generate_header(crate_path)
    header = _directive_re.sub('', header)
    ffi = cffi.FFI()
    ffi.cdef(header)
    ffi.set_source(module_path, None)
    return ffi
