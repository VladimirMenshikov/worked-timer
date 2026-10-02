"""Локальный веб-интерфейс: месячный отчёт и плановые часы.

Слушает исключительно 127.0.0.1, проверяет заголовок
Host (защита от DNS rebinding). Данные — через тот же backend, что и трей.
"""

import json
import os
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import plan_import
import report_core
from web_page import INDEX_HTML

DEFAULT_PORT = 8765
MAX_BODY = 64 * 1024


def month_range_utc(year: int, month: int) -> tuple:
    """[начало месяца − 1 день, начало следующего + 1 день) в UTC.

    Запас в сутки покрывает любой часовой пояс — точную границу по локальным
    суткам браузер отсекает сам.
    """
    first = datetime(year, month, 1, tzinfo=timezone.utc)
    nxt = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=timezone.utc)
    return first - timedelta(days=1), nxt + timedelta(days=1)


def build_report(db, year: int, month: int) -> dict:
    from_utc, to_utc = month_range_utc(year, month)
    sessions = report_core.fetch_sessions(db, from_utc, to_utc)
    try:
        plan_hours = db.select_plan_hours(year, month)
    except Exception:
        plan_hours = None  # таблицы плана может не быть — это не ошибка отчёта
    return {
        "year": year,
        "month": month,
        "planHours": plan_hours,
        "sessions": [
            {
                "task": s["task"],
                "start": s["start_dt"].isoformat(),
                "stop": s["stop_dt"].isoformat() if s["stop_dt"] else None,
                "elapsed": s["elapsed_sec"],
                "status": s["status"],
            }
            for s in sessions
        ],
    }


def _make_handler(db, allowed_hosts: set):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:  # тишина в консоли трея
            pass

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; script-src 'unsafe-inline'; "
                "style-src 'unsafe-inline'; connect-src 'self'",
            )
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, payload: dict) -> None:
            self._send(code, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")

        def do_GET(self) -> None:
            if (self.headers.get("Host") or "") not in allowed_hosts:
                self._json(403, {"error": "forbidden host"})
                return
            url = urlparse(self.path)
            if url.path == "/":
                self._send(200, INDEX_HTML.encode("utf-8"), "text/html; charset=utf-8")
            elif url.path == "/api/report":
                self._report(parse_qs(url.query))
            elif url.path == "/api/plan":
                self._plan_get(parse_qs(url.query))
            else:
                self._json(404, {"error": "not found"})

        def _report(self, query: dict) -> None:
            try:
                year = int(query["year"][0])
                month = int(query["month"][0])
                if not (2000 <= year <= 2100 and 1 <= month <= 12):
                    raise ValueError
            except (KeyError, ValueError, IndexError):
                self._json(400, {"error": "bad year/month"})
                return
            try:
                self._json(200, build_report(db, year, month))
            except Exception as exc:
                self._json(500, {"error": str(exc)})

        def _plan_get(self, query: dict) -> None:
            try:
                year = int(query["year"][0])
                if not 2000 <= year <= 2100:
                    raise ValueError
            except (KeyError, ValueError, IndexError):
                self._json(400, {"error": "bad year"})
                return
            try:
                self._json(200, {"year": year, "rows": db.select_plan_year(year)})
            except Exception as exc:
                self._json(500, {"error": str(exc)})

        def _read_json_body(self):
            """Тело POST. CSRF: пользовательский заголовок X-Requested-With не может
            быть отправлен с чужого сайта без CORS-preflight (на него мы не отвечаем),
            плюс Origin, если он есть, обязан быть нашим."""
            origin = self.headers.get("Origin")
            if origin and origin not in {f"http://{h}" for h in allowed_hosts}:
                self._json(403, {"error": "forbidden origin"})
                return None
            if self.headers.get("X-Requested-With") != "work-timer":
                self._json(403, {"error": "missing X-Requested-With"})
                return None
            if (self.headers.get("Content-Type") or "").split(";")[0] != "application/json":
                self._json(415, {"error": "application/json expected"})
                return None
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = -1
            if not 0 < length <= MAX_BODY:
                self._json(413, {"error": "bad body size"})
                return None
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(data, dict):
                    raise ValueError
                return data
            except ValueError:
                self._json(400, {"error": "bad json"})
                return None

        def do_POST(self) -> None:
            if (self.headers.get("Host") or "") not in allowed_hosts:
                self._json(403, {"error": "forbidden host"})
                return
            path = urlparse(self.path).path
            if path not in ("/api/plan", "/api/plan/import"):
                self._json(404, {"error": "not found"})
                return
            data = self._read_json_body()
            if data is None:
                return
            rows, errors = [], []
            try:
                if path == "/api/plan":
                    for i, r in enumerate(data.get("rows") or [], start=1):
                        try:
                            rows.append(plan_import.validate_row(
                                r.get("year"), r.get("month"), r.get("work_days"), r.get("work_hours")))
                        except (ValueError, AttributeError) as exc:
                            errors.append(f"запись {i}: {exc}")
                    if len(rows) > plan_import.MAX_ROWS:
                        errors.append("слишком много записей")
                else:
                    year = int(data.get("year") or datetime.now().year)
                    rows, errors = plan_import.parse_plan_text(str(data.get("text") or ""), year)
            except (ValueError, TypeError):
                self._json(400, {"error": "bad request"})
                return
            if errors or not rows:
                self._json(400, {"error": "; ".join(errors) or "нет данных для сохранения", "errors": errors})
                return
            try:
                db.upsert_plan_hours(rows)
            except Exception as exc:
                self._json(500, {"error": str(exc)})
                return
            self._json(200, {"saved": len(rows)})

        do_PUT = do_DELETE = do_PATCH = lambda self: self._json(405, {"error": "method not allowed"})

    return Handler


def start(db) -> str:
    """Запускает сервер в фоновом потоке, возвращает URL."""
    try:
        port = int(os.environ.get("WEB_PORT", DEFAULT_PORT))
    except ValueError:
        port = DEFAULT_PORT

    server = None
    for candidate in (port, 0):  # занят порт — берём любой свободный
        try:
            server = ThreadingHTTPServer(("127.0.0.1", candidate), BaseHTTPRequestHandler)
            break
        except OSError:
            continue
    if server is None:
        raise RuntimeError("Не удалось занять порт для локального веб-интерфейса")

    real_port = server.server_address[1]
    allowed = {f"127.0.0.1:{real_port}", f"localhost:{real_port}"}
    server.RequestHandlerClass = _make_handler(db, allowed)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{real_port}/"
