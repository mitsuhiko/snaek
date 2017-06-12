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


EMPTY_C = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'empty.c')
BINDGEN = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                       'bin', 'cbindgen')

EXT_EXT = sys.platform == 'darwin' and '.dylib' or '.so'
BUILD_PY = u'''
import re, sys, subprocess, cffi

header = subprocess.Popen(
    [%(bindgen)r, '--lang=c', '-o', '/dev/stdout', %(crate_path)r],
    stdout=subprocess.PIPE
).communicate()[0]

header = re.compile(r'^\s*#.*?$(?m)').sub('', header)
if sys.version_info >= (3, 0):
    header = header.decode('utf-8')

ffi = cffi.FFI()
ffi.cdef(header)
ffi.set_source(%(cffi_module_path)r, None)
'''
MODULE_PY = u'''# auto-generated file
import os
from %(cffi_module_path)s import ffi
lib = ffi.dlopen(os.path.join(
    os.path.dirname(__file__),
    %(rust_lib_filename)r))

__all__ = ['lib', 'ffi']
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
        self.rust_lib_filename = '%s__lib%s' % (
            genbase.split('.')[-1],
            sysconfig.get_config_var('SO') or '',
        )
        self.fake_module_path = '%s__lib' % genbase

    def get_cffi_build_path(self):
        log.info('generating cffi build script for %s', self.module_path)
        build_script = BUILD_PY % {
            'bindgen': BINDGEN,
            'crate_path': self.crate_path,
            'cffi_module_path': self.cffi_module_path,
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


def add_rust_module(dist, module):
    module_def = make_module_def(module)

    if dist.ext_modules is None:
        dist.ext_modules = []
    dist.ext_modules.append(Extension(module_def.fake_module_path,
                                      sources=[EMPTY_C]))

    base_build_ext = dist.cmdclass.get('build_ext', build_ext)
    base_build_py = dist.cmdclass.get('build_py', build_py)

    def build_rustlib(base_path):
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

    class SnaekBuildPy(base_build_py):
        def run(self):
            base_build_py.run(self)
            build_rustlib(os.path.join(self.build_lib,
                                       *module_def.module_base_path.split('.')))

    class SnaekBuildExt(base_build_ext):
        def run(self):
            base_build_ext.run(self)
            if self.inplace:
                build_py = self.get_finalized_command('build_py')
                build_rustlib(build_py.get_package_dir(module_def.module_base_path))

    dist.cmdclass['build_py'] = SnaekBuildPy
    dist.cmdclass['build_ext'] = SnaekBuildExt

    return module_def


def snaek_rust_modules(dist, attr, value):
    assert attr == 'snaek_rust_modules'
    if value is None:
        value = []
    elif isinstance(value, basestring):
        value = [value]
    else:
        value = list(value)

    cffi_modules_defs = []
    for rust_module in value:
        cffi_modules_defs.append(
            '%s:ffi' % add_rust_module(dist, rust_module).get_cffi_build_path())

    # Register our dummy modules with cffi
    cffi_modules(dist, 'cffi_modules', cffi_modules_defs)


def snaek_universal(dist, attr, value):
    assert attr == 'snaek_universal'
    if not value or bdist_wheel is None:
        return

    log.info('enabling universal wheel mode')
    base_bdist_wheel = dist.cmdclass.get('bdist_wheel', bdist_wheel)

    class SnaekBdistWheel(base_bdist_wheel):
        def get_tag(self):
            return ('py2.py3', 'none',) + base_bdist_wheel.get_tag(self)[2:]

    dist.cmdclass['bdist_wheel'] = SnaekBdistWheel
