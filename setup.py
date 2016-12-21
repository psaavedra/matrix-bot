from setuptools import setup, find_packages

version = "0.0.3"

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
    },
    scripts=[
        "tools/matrix-bot",
    ],
    zip_safe=False,
    install_requires=[
        "getconf",
        "matrix-client",
        "python-ldap",
    ],
    data_files=[
        ('/usr/share/doc/matrix-bot/',
            ['cfg/matrix-bot.cfg.example']),
    ],

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
