import os
import socket as sk
import threading
import sqlite3


def serve():
    s = sk.socket(sk.AF_INET, sk.SOCK_STREAM)
    s.bind(("0.0.0.0", 8080))
    s.listen(5)
    return s


def spawn_worker():
    t = threading.Thread(target=serve)
    t.start()
    return t


def log_event(msg):
    with open("/var/log/app.log", "a") as f:
        f.write(msg + "\n")


def open_db():
    return sqlite3.connect("/var/lib/app/data.db")


def fork_child():
    pid = os.fork()
    return pid
