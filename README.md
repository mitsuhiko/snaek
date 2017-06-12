# Snaek

Snaek is a Python library that helps you build Rust libraries and bridge them to
Python with the help of cffi.

## Why?

There are already other projects that make Python and Rust play along but this
one is different.  Unlike other projects that build Python extension modules the
goal of this project is to build regular Rust libraries that are then loaded
with CFFI at runtime.  The advantage of this is that it does not link against
libpython which means that you only need to build a handful of Python wheels
to cover all platforms you care about.

In particular you will most likely only need two wheels for Linux, one for macs
and soon one for Windows independently of how many Python interpreters you want
to target.

## What is supported?

* Platforms: Linux, Mac (Windows later)
* setuptools commands: `bdist_wheel`, `build`, `build_ext`, `develop`
* `pip install --editable .`
* Universal wheels (`PACKAGE-py2.py3-none-PLATFORM.whl`); this can be disabled
  with `snaek_universal=False` in `setup()` in case the package also contains
  stuff that does link against libpython.

## How?

This is what a `setup.py` file looks like:

```python
from setuptools import setup

setup(
    name='example',
    version='0.0.1',
    packages=['example'],
    zip_safe=False,
    platforms='any',
    setup_requires=['snaek'],
    install_requires=['snaek'],
    snaek_rust_modules=[
        ('example._native', 'rust/'),
    ]
)
```

You then need a `rust/` folder that has a Rust library (with a crate type
of `cdylib`) and a `example/` python package.

Example `example/__init__.py` file:

```python
from example._native import ffi, lib


def test():
    return lib.a_function_from_rust()
```

And a `rust/src/lib.rs`:

```rust
#[no_mangle]
pub unsafe extern "C" fn a_function_from_rust() -> i32 {
    42
}
```
