"""Desktop entry point: one server per data directory, readiness before browser."""
import argparse
import ctypes
import json
import logging
import os
from pathlib import Path
import secrets
import sys
import threading
import time
import urllib.request
import webbrowser

from app.runtime import data_directory, local_secret
from app.version import VERSION
from app.logging_config import configure_logging


class InstanceLock:
    def __init__(self, directory):
        directory.mkdir(parents=True, exist_ok=True)
        self.file = open(directory / 'application.lock', 'a+b')
        # Windows byte locks also deny reads: inspect file size without reading
        # the byte held by an already running instance.
        self.file.seek(0, os.SEEK_END)
        if self.file.tell() == 0:
            self.file.write(b'0'); self.file.flush()
        self.file.seek(0)

    def acquire(self):
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    def close(self):
        self.file.close()


def healthy(url, identity):
    try:
        with urllib.request.urlopen(url + '/_health',timeout=1) as response:
            return json.load(response).get('instance') == identity
    except Exception:
        return False


def run(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--smoke',action='store_true')
    parser.add_argument('--setup',action='store_true')
    args = parser.parse_args(argv)
    directory = data_directory()
    directory.mkdir(parents=True,exist_ok=True)
    (directory / 'logs').mkdir(exist_ok=True)
    configure_logging(directory / 'logs')
    metadata = directory / 'server.json'
    lock = InstanceLock(directory)
    if not lock.acquire():
        try:
            for _ in range(60):
                try:
                    info = json.loads(metadata.read_text(encoding='utf-8'))
                    if healthy(info['url'],info['instance']):
                        if not args.no_browser:
                            webbrowser.open(info['url'])
                        return 0
                except (OSError,ValueError,KeyError):
                    pass
                time.sleep(.25)
            raise RuntimeError('Financial Tracker is starting or busy. Please try again. / Приложение запускается или занято. Повторите попытку.')
        finally:
            lock.close()
    server = None
    try:
        logging.info('Financial Tracker %s starting (frozen=%s)',VERSION,bool(getattr(sys,'frozen',False)))
        from app import create_app
        from waitress import create_server
        app = create_app({'SECRET_KEY':local_secret(directory), 'SESSION_COOKIE_SECURE':False,
                          'TRUSTED_HOSTS':['127.0.0.1','localhost','[::1]']})
        if args.setup:
            return 0
        identity = secrets.token_hex(24)
        app.config['LAUNCHER_ID'] = identity
        @app.get('/_health')
        def health():
            return {'application':'FinancialTracker','version':VERSION,'instance':identity}
        server = create_server(app,host='127.0.0.1',port=0,threads=4)
        url = 'http://127.0.0.1:' + str(server.effective_port)
        stopped = threading.Event()
        def stop():
            # Close from a separate thread after the HTTP response has completed.
            def finish():
                time.sleep(.5)
                stopped.set()
            threading.Thread(target=finish,daemon=True).start()
        app.config['STOP_APPLICATION'] = stop
        worker = threading.Thread(target=server.run,daemon=True)
        worker.start()
        for _ in range(100):
            if healthy(url,identity):
                break
            if not worker.is_alive():
                raise RuntimeError('Server could not start. / Не удалось запустить сервер.')
            time.sleep(.1)
        else:
            raise RuntimeError('Server readiness timed out. / Сервер не ответил вовремя.')
        metadata.write_text(json.dumps({'url':url,'instance':identity,'pid':os.getpid()}),encoding='utf-8')
        if args.smoke:
            for path in ['/','/transactions/','/goals/','/settings/','/import/','/static/css/app.css','/static/vendor/chart.umd.min.js','/static/fonts/InterVariable.woff2']:
                with urllib.request.urlopen(url+path,timeout=5) as response:
                    if response.status != 200:
                        raise RuntimeError('Smoke check failed: '+path)
            frozen = bool(getattr(sys,'frozen',False))
            if frozen:
                from pathlib import Path
                bundle = Path(sys._MEIPASS).resolve()
                if not all(Path(path).resolve().is_relative_to(bundle) for path in sys.path):
                    raise RuntimeError('Packaged Python path escaped the bundle')
            (directory/'smoke-result.json').write_text(json.dumps({'ok':True,'url':url,'version':VERSION,'frozen':frozen,
                                                                   'bundled_python_paths':frozen}),encoding='utf-8')
            return 0
        if not args.no_browser:
            webbrowser.open(url)
        while not stopped.wait(.5):
            if not worker.is_alive():
                raise RuntimeError('Server stopped unexpectedly. / Сервер неожиданно остановился.')
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as error:
        logging.exception('Application startup failure')
        message = f'Could not start / Не удалось запустить: {type(error).__name__}\nLogs / Журнал: {directory / "logs"}'
        if os.name == 'nt' and not args.smoke:
            ctypes.windll.user32.MessageBoxW(None,message,'Financial Tracker',0x10)
        elif sys.stderr:
            print(message,file=sys.stderr)
        return 1
    finally:
        if server:
            server.close()
        metadata.unlink(missing_ok=True)
        lock.close()


def main(argv=None):
    try:
        return run(argv)
    except Exception as error:
        # Even failures before app initialization (e.g. an unwritable data path)
        # must be visible in a windowed executable.
        logging.exception('Launcher failure')
        message = f'Unable to start / Не удалось запустить Financial Tracker:\n{error}'
        if os.name == 'nt' and '--smoke' not in (argv or sys.argv[1:]):
            ctypes.windll.user32.MessageBoxW(None,message,'Financial Tracker',0x10)
        elif sys.stderr:
            print(message,file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
