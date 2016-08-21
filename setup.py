#!/usr/bin/env python3
import os
from setuptools import setup, find_packages
from pilight2mqtt.const import __version__

PACKAGE_NAME = 'pilight2mqtt'
HERE = os.path.abspath(os.path.dirname(__file__))
DOWNLOAD_URL = ('https://github.com/mcdeck/pilight2mqtt/archive/'
                '{}.zip'.format(__version__))

PACKAGES = find_packages(exclude=['tests', 'tests.*'])

REQUIRES = [
    'paho-mqtt'
]

setup(
    name=PACKAGE_NAME,
    version=__version__,
    license='MIT License',
    url='https://www.van-porten.de/portfolio/pilight2mqtt',
    download_url=DOWNLOAD_URL,
    author='Oliver van Porten',
    author_email='oliver@van-porten.de',
    description='Translate pilight to mqtt.',
    packages=PACKAGES,
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    install_requires=REQUIRES,
    test_suite='tests',
    keywords=['home', 'automation'],
    entry_points={
        'console_scripts': [
            'pilight2mqtt = pilight2mqtt.__main__:main'
        ]
    },
    classifiers=[
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.4',
        'Topic :: Home Automation'
    ],
)
