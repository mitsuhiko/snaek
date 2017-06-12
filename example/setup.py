from setuptools import setup, find_packages

setup(
    name='example',
    version='0.0.1',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    install_requires=[
        'snaek',
    ],
    snaek_rust_modules=[
        ('example._native', 'rust/'),
    ]
)
