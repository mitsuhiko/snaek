from setuptools import setup, find_packages

setup(
    name='snaek',
    version='0.0.1',
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
)
