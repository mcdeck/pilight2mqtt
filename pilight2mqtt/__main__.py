#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Main module of pilight2mqtt
"""

from __future__ import print_function

import sys
import os
import logging
import argparse
import textwrap

from pilight2mqtt.core import (PilightServer,
                               Pilight2MQTT)
from pilight2mqtt.const import __version__


def get_arguments():
    """Get parsed passed in arguments."""
    parser = argparse.ArgumentParser(
        description="pilight2mqtt: Translate pilight events to MQTT.")
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument(
        '--mqtt-server',
        default='localhost',
        help='Address of the MQTT server to talk to.')
    parser.add_argument(
        '--mqtt-port',
        default=1883,
        type=int,
        help='Port of the MQTT server to talk to.')
    parser.add_argument(
        '--mqtt-topic',
        default='PILIGHT',
        help='MQTT topic to use.')
    parser.add_argument(
        '--pilight-server',
        default=None,
        help=textwrap.dedent('''\
            Set the address of the pilight server to use.
            If not specified will try to auto discover'''))
    parser.add_argument(
        '--pilight-port',
        default=5001,
        type=int,
        help=textwrap.dedent('''\
            Port of the pilight server.
            Only used when pilight-server is also specified'''))
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Start pilight2mqtt in debug mode')
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Start pilight2mqtt in verbose mode')
    parser.add_argument(
        '--pid-file',
        metavar='path_to_pid_file',
        default=None,
        help='Path to PID file useful for running as daemon')
    if os.name == "posix":
        parser.add_argument(
            '--daemon',
            action='store_true',
            help='Run pilight2mqtt as daemon')

    arguments = parser.parse_args()
    if os.name != "posix" or arguments.debug:
        arguments.daemon = False

    return arguments


# Borrowed from Home Assistatnt
def daemonize():
    """Move current process to daemon process."""
    # Create first fork
    pid = os.fork()  # pylint: disable=no-member
    if pid > 0:
        sys.exit(0)

    # Decouple fork
    os.setsid()  # pylint: disable=no-member

    # Create second fork
    pid = os.fork()  # pylint: disable=no-member
    if pid > 0:
        sys.exit(0)

    # redirect standard file descriptors to devnull
    infd = open(os.devnull, 'r')
    outfd = open(os.devnull, 'a+')
    sys.stdout.flush()
    sys.stderr.flush()
    os.dup2(infd.fileno(), sys.stdin.fileno())
    os.dup2(outfd.fileno(), sys.stdout.fileno())
    os.dup2(outfd.fileno(), sys.stderr.fileno())


def check_pid(pid_file):
    """Check that HA is not already running."""
    # Check pid file
    try:
        pid = int(open(pid_file, 'r').readline())
    except IOError:
        # PID File does not exist
        return

    # If we just restarted, we just found our own pidfile.
    if pid == os.getpid():
        return

    try:
        os.kill(pid, 0)
    except OSError:
        # PID does not exist
        return
    print('Fatal Error: pilight2mqtt is already running.')
    sys.exit(1)


def write_pid(pid_file):
    """Create a PID File."""
    pid = os.getpid()
    try:
        open(pid_file, 'w').write(str(pid))
    except IOError:
        print('Fatal Error: Unable to write pid file {}'.format(pid_file))
        sys.exit(1)


def main():
    """main entry point"""
    args = get_arguments()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    elif args.verbose:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)

    # Daemon functions
    if args.pid_file:
        check_pid(args.pid_file)
    if args.daemon:
        daemonize()
    if args.pid_file:
        write_pid(args.pid_file)

    if args.pilight_server:
        server = PilightServer(args.pilight_server,
                               args.pilight_port)
    else:
        server = PilightServer.discover()

    p2m = Pilight2MQTT(server,
                       args.mqtt_server,
                       mqtt_port=args.mqtt_port,
                       mqtt_topic=args.mqtt_topic)
    return p2m.run()


if __name__ == "__main__":
    sys.exit(main())
