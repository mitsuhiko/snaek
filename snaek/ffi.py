import os
import re
import sys
import cffi

from ._compat import PY2


_directive_re = re.compile(r'^\s*#.*?$(?m)')


def make_ffi(module_path, crate_path, cached_header_filename=None):
    """Creates a FFI instance for the given configuration."""
    if cached_header_filename is not None and \
       os.path.isfile(cached_header_filename):
        with open(cached_header_filename, 'rb') as f:
            header = f.read()
        if not PY2:
            header = header.decode('utf-8')
    else:
        from .bindgen import generate_header
        header = generate_header(crate_path)
    header = _directive_re.sub('', header)

    if os.environ.get('SNAEK_DEBUG_HEADER') == '1':
        sys.stderr.write('/* generated header for "%s" */\n' % module_path)
        sys.stderr.write(header)
        sys.stderr.write('\n')
        sys.stderr.flush()

    ffi = cffi.FFI()
    ffi.cdef(header)
    ffi.set_source(module_path, None)
    return ffi
