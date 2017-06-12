from setuptools import setup, find_packages
from setuptools.dist import Distribution

# Dogfood ourselves here.  Since however we at this point might not be
# installed yet we cannot use snaek_rust_modules directly.  Additionally
# we might not be able to import outselves yet because the setup
# requirements are not installed yet.  In that case do nothing.
extra = {}
try:
    from snaek import setuptools_ext
except ImportError:
    pass
else:
    class SneakDistribution(Distribution):
        def __init__(self, *args, **kwargs):
            Distribution.__init__(self, *args, **kwargs)
            setuptools_ext.snaek_rust_modules(self, 'snaek_rust_modules', [
                ('snaek._bindgen', 'rust/'),
            ])
    extra['distclass'] = SneakDistribution

setup(
    name='snaek',
    version='0.1.0',
    author='Armin Ronacher',
    author_email='armin.ronacher@active-4.com',
    packages=find_packages(),
    include_package_data=True,
    description='A python library for distributing Rust modules.',
    zip_safe=False,
    platforms='any',
    install_requires=[
        'cffi>=1.6.0',
    ],
    setup_requires=[
        'cffi>=1.6.0',
    ],
    entry_points={
        'distutils.setup_keywords': [
            'snaek_rust_modules = snaek.setuptools_ext:snaek_rust_modules',
            'snaek_universal = snaek.setuptools_ext:snaek_universal',
        ],
    },
    classifiers=[
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
    ],
    **extra
)
