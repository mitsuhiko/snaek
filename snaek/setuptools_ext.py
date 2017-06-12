import os
import re
import sys
import uuid
import json
import shutil
import atexit
import tempfile
import sysconfig
import subprocess

from distutils import log
from distutils.core import Extension
from distutils.command.build_py import build_py
from distutils.command.build_ext import build_ext
from cffi.setuptools_ext import cffi_modules

try:
    from wheel.bdist_wheel import bdist_wheel
except ImportError:
    bdist_wheel = None


here = os.path.abspath(os.path.dirname(__file__))
EMPTY_C = os.path.join(here, 'empty.c')
EXT_EXT = sys.platform == 'darwin' and '.dylib' or '.so'

BUILD_PY = u'''
import cffi
from snaek.ffi import make_ffi
ffi = make_ffi(%(cffi_module_path)r, %(crate_path)r, %(cached_header_filename)r)
'''
MODULE_PY = u'''# auto-generated file
__all__ = ['lib', 'ffi']

import os
from %(cffi_module_path)s import ffi
lib = ffi.dlopen(os.path.join(os.path.dirname(__file__), %(rust_lib_filename)r))
del os
'''


def error(msg):
    from distutils.errors import DistutilsSetupError
    raise DistutilsSetupError(msg)


class ModuleDef(object):

    def __init__(self, module_path, crate_path):
        self.module_path = module_path
        self.crate_path = os.path.abspath(crate_path)

        parts = self.module_path.rsplit('.', 2)
        self.module_base_path = parts[0]
        self.name = parts[-1]

        genbase = '%s._%s' % (parts[0], parts[1].lstrip('_'))
        self.cffi_module_path = '%s__ffi' % genbase
        self.cached_header_filename = os.path.join(self.crate_path, 'header.h')
        self.rust_lib_filename = '%s__lib%s' % (
            genbase.split('.')[-1],
            sysconfig.get_config_var('SO') or '',
        )
        self.fake_module_path = '%s__lib' % genbase

    def make_cffi_build_script(self):
        log.info('generating cffi build script for %s', self.module_path)
        build_script = BUILD_PY % {
            'crate_path': self.crate_path,
            'cffi_module_path': self.cffi_module_path,
            'cached_header_filename': self.cached_header_filename,
        }
        fn = os.path.join(tempfile.gettempdir(), '._snaek-%s.py' % uuid.uuid4())

        with open(fn, 'wb') as f:
            f.write(build_script.encode('utf-8'))

        @atexit.register
        def clear_file():
            try:
                os.remove(fn)
            except Exception:
                pass

        return fn

    @property
    def toml_path(self):
        return os.path.join(self.crate_path, 'Cargo.toml')


def make_module_def(value):
    if not isinstance(value, tuple) or len(value) != 2:
        error('snaek_rust_modules takes a list of tuples in the '
              'form (module_path, path_to_rust_crate)')

    module_path, crate_path = value
    if '.' not in module_path:
        error('can only build rust modules in python packages')

    mod_def = ModuleDef(module_path, crate_path)
    if not os.path.isfile(mod_def.toml_path):
        error('module %s does not have a Cargo.toml file' % mod_def.name)

    _crate_type_re = re.compile(r'^\s*crate-type\s*=\s*(.*?)\s*$(?m)')
    with open(mod_def.toml_path) as f:
        for line in f:
            match = _crate_type_re.match(line)
            if match is None:
                continue
            if 'cdylib' not in match.group(1):
                error('crate-type needs to be set to cdylib but is set to %s'
                      % match.group(1))
            break
        else:
            error('crate-type needs to be set to cdylib but is missing')

    return mod_def


def build_rustlib(module_def, base_path):
    log.info('building rust lib %s', module_def.module_path)
    cmdline = ['cargo', 'build', '--release']
    if not sys.stdout.isatty():
        cmdline.append('--color=always')
    rv = subprocess.Popen(cmdline, cwd=module_def.crate_path).wait()
    if rv != 0:
        sys.exit(rv)

    src_path = os.path.join(module_def.crate_path, 'target', 'release')
    for filename in os.listdir(src_path):
        if filename.endswith(EXT_EXT):
            shutil.copy2(os.path.join(src_path, filename),
                         os.path.join(base_path, module_def.rust_lib_filename))
            break
    else:
        # XXX: parse toml file to ensure that crate type is set
        error('rust library did not generate a shared library.')

    log.info('building python wrapper for %s', module_def.module_path)
    with open(os.path.join(base_path, module_def.name + '.py'), 'wb') as f:
        f.write(MODULE_PY % {
            'cffi_module_path': module_def.cffi_module_path,
            'rust_lib_filename': module_def.rust_lib_filename,
        })


def add_rust_module(dist, module):
    module_def = make_module_def(module)

    # Because distutils was never intended to support other languages and
    # this was never cleaned up, we need to generate a fake C module which
    # we later override with our rust module.  This means we just compile
    # an empty .c file into a Python module.  This will trick wheel and
    # other systems into assuming our library has binary extensions.
    if dist.ext_modules is None:
        dist.ext_modules = []
    dist.ext_modules.append(Extension(module_def.fake_module_path,
                                      sources=[EMPTY_C]))

    base_build_ext = dist.cmdclass.get('build_ext', build_ext)
    base_build_py = dist.cmdclass.get('build_py', build_py)

    class SnaekBuildPy(base_build_py):
        def run(self):
            base_build_py.run(self)
            build_rustlib(module_def, os.path.join(
                self.build_lib, *module_def.module_base_path.split('.')))

    class SnaekBuildExt(base_build_ext):
        def run(self):
            base_build_ext.run(self)
            if self.inplace:
                build_py = self.get_finalized_command('build_py')
                build_rustlib(
                    module_def,
                    build_py.get_package_dir(module_def.module_base_path))

    dist.cmdclass['build_py'] = SnaekBuildPy
    dist.cmdclass['build_ext'] = SnaekBuildExt

    return module_def.make_cffi_build_script() + ':ffi'


def snaek_rust_modules(dist, attr, value):
    assert attr == 'snaek_rust_modules'
    patch_universal_wheel(dist)

    if value is None:
        value = []
    elif isinstance(value, basestring):
        value = [value]
    else:
        value = list(value)

    cffi_defs = []
    for rust_module in value:
        cffi_defs.append(add_rust_module(dist, rust_module))

    # Register our dummy modules with cffi
    cffi_modules(dist, 'cffi_modules', cffi_defs)


def snaek_universal(dist, attr, value):
    assert attr == 'snaek_universal'
    patch_universal_wheel(dist)
    dist.snaek_universal = value


def patch_universal_wheel(dist):
    value = getattr(dist, 'snaek_universal', None)
    if value is None:
        dist.snaek_universal = True

    base_bdist_wheel = dist.cmdclass.get('bdist_wheel', bdist_wheel)

    if base_bdist_wheel is None:
        return

    class SnaekBdistWheel(base_bdist_wheel):
        def get_tag(self):
            rv = base_bdist_wheel.get_tag(self)
            if not dist.snaek_universal:
                return rv
            return ('py2.py3', 'none',) + rv[2:]

    dist.cmdclass['bdist_wheel'] = SnaekBdistWheel
