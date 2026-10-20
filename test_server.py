#!/usr/bin/env python3
"""Minimal demo service used by the README examples and by the test suite.

Runs in the foreground (as required by the manager script), optionally listens
on a TCP port, and exits cleanly on SIGTERM/SIGINT.

Examples:
    python3 test_server.py
    python3 test_server.py --port 8080
    python3 test_server.py --start-delay 2 --crash-after 5
"""

import argparse
import os
import signal
import socket
import sys
import time


def parse_args():
    parser = argparse.ArgumentParser(description="Demo foreground service for the server manager.")
    parser.add_argument("--port", type=int, default=0, help="listen on 127.0.0.1:PORT")
    parser.add_argument("--start-delay", type=float, default=0.0,
                        help="sleep N seconds before announcing readiness")
    parser.add_argument("--crash-after", type=float, default=0.0,
                        help="exit with status 1 after N seconds")
    parser.add_argument("--ignore-term", action="store_true",
                        help="ignore SIGTERM (used to test SIGKILL escalation)")
    return parser.parse_args()


def main():
    args = parse_args()
    stopping = False

    def handle(_signum, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, handle)
    if args.ignore_term:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    else:
        signal.signal(signal.SIGTERM, handle)

    sock = None

    # Simulate a slow initialization: nothing listens until the delay elapsed.
    if args.start_delay:
        time.sleep(args.start_delay)

    if args.port:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", args.port))
        except OSError as exc:
            print(f"bind failed: {exc}", flush=True)
            return 2
        sock.listen(8)
        sock.setblocking(False)

    print(f"demo service started (pid={os.getpid()})", flush=True)
    if sock is not None:
        print(f"listening on 127.0.0.1:{args.port}", flush=True)

    started = time.time()
    while not stopping:
        if sock is not None:
            try:
                conn, _ = sock.accept()
                conn.sendall(b"ok\n")
                conn.close()
            except BlockingIOError:
                pass
        if args.crash_after and (time.time() - started) >= args.crash_after:
            print("simulated crash", flush=True)
            return 1
        time.sleep(0.1)

    print("shutting down", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
