from setuptools import setup, find_packages
import os

here = os.path.abspath(os.path.dirname(__file__))

try: # for pip >= 10
    from pip._internal.req import parse_requirements
except ImportError: # for pip <= 9.0.3
    from pip.req import parse_requirements

def read_file(path_segments):
    """Read a file from the package. Takes a list of strings to join to
    make the path"""
    file_path = os.path.join(here, *path_segments)
    with open(file_path) as f:
        return f.read()


def exec_file(path_segments):
    """Execute a single python file to get
    the variables defined in it"""
    result = {}
    code = read_file(path_segments)
    exec(code, result)
    return result

version = exec_file(("matrixbot", "__init__.py"))["__version__"]

long_description = ""
try:
    long_description = file('README.md').read()
except Exception:
    pass

license = ""
try:
    license = file('LICENSE').read()
except Exception:
    pass


setup(
    name='matrix-bot',
    version=version,
    description='A matrix.org bot',
    author='Pablo Saavedra',
    author_email='saavedra.pablo@gmail.com',
    url='http://github.com/psaavedra/matrix-bot',
    packages=find_packages(),
    package_data={
        "matrixbot": [
            "../cfg/matrix-bot.cfg.example",
            "../cfg/echo-test-template.cfg"
        ]
    },
    scripts=[
        "tools/matrix-bot",
        "tools/matrix-digest",
        "tools/matrix-echo",
        "tools/matrix-subscriber",
    ],
    zip_safe=False,
    install_requires = list(map(lambda x:x.requirement,parse_requirements('requirements.txt', session=''))),

    download_url='https://github.com/psaavedra/matrix-bot/zipball/master',
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Topic :: Communications :: Chat",
    ],
    long_description=long_description,
    license=license,
    keywords="python matrix bot matrix-python-sdk",
)
