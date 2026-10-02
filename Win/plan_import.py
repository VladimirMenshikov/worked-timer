"""Разбор и проверка списка плановых часов (таблица wh_plan_work_hourses).

Без UI и БД — используется веб-интерфейсом; все значения проверяются здесь,
до записи в БД.
"""

import re

MAX_ROWS = 240


def _num(token: str, what: str, line_no: int) -> float:
    try:
        return float(token.replace(",", "."))
    except ValueError:
        raise ValueError(f"строка {line_no}: {what} — не число: {token!r}")


def validate_row(year, month, work_days, work_hours) -> dict:
    """Приводит значения к типам таблицы и проверяет диапазоны."""
    try:
        year, month, work_days = int(year), int(month), int(work_days)
        work_hours = round(float(work_hours), 2)
    except (TypeError, ValueError):
        raise ValueError("значения должны быть числами")
    if not 2000 <= year <= 2100:
        raise ValueError(f"год {year} вне диапазона 2000–2100")
    if not 1 <= month <= 12:
        raise ValueError(f"месяц {month} вне диапазона 1–12")
    if not 0 <= work_days <= 31:
        raise ValueError(f"рабочих дней {work_days} вне диапазона 0–31")
    if not 0 <= work_hours <= 744:
        raise ValueError(f"часов {work_hours} вне диапазона 0–744")
    return {"year": year, "month": month, "work_days": work_days, "work_hours": work_hours}


def parse_plan_text(text: str, default_year: int) -> tuple:
    """Разбирает список «месяц/год, рабочих дней, часов» → (rows, errors).

    Строка — одно из:
      ГГГГ;М;дней;часов        2026;1;15;120
      ГГГГ-ММ дней часов       2026-01 15 120
      М дней часов             1 15 120   (год — default_year)
    Разделители: `;`, табуляция (тогда в часах допустима запятая: 175,5),
    иначе пробелы (запятая в часах — десятичная) либо запятые без пробелов. Заголовок (первая нечисловая строка) и пустые
    строки пропускаются.
    """
    rows, errors = [], []
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        if re.search(r"[;\t]", line):
            parts = [p.strip() for p in re.split(r"[;\t]", line) if p.strip()]
        else:
            parts = [p.rstrip(",") for p in line.split()]
            if len(parts) == 1:  # «2026,1,15,120» без пробелов
                parts = [p for p in parts[0].split(",") if p]
        if not re.match(r"^\d", parts[0]):
            if line_no == 1 or not rows and not errors:
                continue  # заголовок
        try:
            m = re.fullmatch(r"(\d{4})[-./](\d{1,2})", parts[0])
            if m:
                year, month, rest = m.group(1), m.group(2), parts[1:]
            elif len(parts) == 4:
                year, month, rest = parts[0], parts[1], parts[2:]
            elif len(parts) == 3:
                year, month, rest = default_year, parts[0], parts[1:]
            else:
                raise ValueError(f"строка {line_no}: ожидается «год;месяц;дней;часов», получено: {raw.strip()!r}")
            if len(rest) != 2:
                raise ValueError(f"строка {line_no}: ожидаются «рабочих дней» и «часов»")
            rows.append(validate_row(
                _num(str(year), "год", line_no), _num(str(month), "месяц", line_no),
                _num(rest[0], "рабочих дней", line_no), _num(rest[1], "часов", line_no),
            ))
        except ValueError as exc:
            msg = str(exc)
            errors.append(msg if msg.startswith("строка") else f"строка {line_no}: {msg}")
    if len(rows) > MAX_ROWS:
        errors.append(f"слишком много строк (максимум {MAX_ROWS})")
    # одинаковый (год, месяц) в списке — побеждает последняя строка
    unique = {(r["year"], r["month"]): r for r in rows}
    return list(unique.values()), errors
