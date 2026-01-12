import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import calendar
import json
from pathlib import Path

# =========================
# (NUEVO) PDF export deps
# =========================
try:
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib import colors as rl_colors
    from reportlab.pdfbase.pdfmetrics import stringWidth
except Exception:
    rl_canvas = None
    landscape = None
    letter = None
    rl_colors = None
    stringWidth = None

# =========================
# Modelo de datos
# =========================

@dataclass
class Event:
    date_str: str   # "YYYY-MM-DD"
    type: str       # "Class" | "Task" | "Info" | "Exam"
    title: str

EVENT_TYPES = ["Class", "Task", "Info", "Exam"]

# =========================
# Plantilla HTML (SIN .format)
# =========================

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="%%HTML_LANG%%">
<head>
  <meta charset="UTF-8">
  <title>%%DOC_TITLE%%</title>
  <style>
    body { font-family: Arial, sans-serif; max-width: 800px; margin: auto; padding: 20px; }
    h2 { text-align: center; margin-bottom: 10px; }

    .calendar-nav { display: flex; justify-content: center; align-items: center; margin-bottom: 10px; gap: 10px; }
    .calendar-nav button {
      width: 40px; height: 40px; font-size: 20px; font-weight: bold; cursor: pointer;
      background-color: #e0e0e0; border: 1px solid #bbb; border-radius: 4px;
    }
    .calendar-nav span { margin: 0 10px; font-size: 18px; font-weight: bold; min-width: 180px; text-align: center; }

    table { width: 100%; border-collapse: collapse; }
    th, td {
      width: 14.28%; height: 80px; text-align: center; vertical-align: top;
      border: 1px solid #ccc; padding: 5px; position: relative;
    }
    th { background-color: #f2f2f2; }

    .class-day { background-color: #ffcc80; cursor: pointer; }
    .task-day  { background-color: #a5d6a7; cursor: pointer; }
    .info-day  { background-color: #90caf9; cursor: pointer; }
    .exam-day  { background-color: #ef9a9a; cursor: pointer; }

    .today { outline: 3px solid #000; outline-offset: -3px; font-weight: bold; }
    .today-marker {
      position: absolute; bottom: 4px; right: 4px;
      font-size: 10px; padding: 2px 4px; border: 1px solid #000;
      border-radius: 4px; background: #fff;
    }

    .footer-info { margin-top: 20px; padding-top: 10px; border-top: 2px solid #ddd; font-size: 16px; }
    .footer-info p { margin: 5px 0; }

    .popup-overlay {
      position: fixed; top: 0; left: 0; width: 100%; height: 100%;
      background: rgba(0, 0, 0, 0.4); display: none;
      justify-content: center; align-items: center; z-index: 999;
    }
    .popup-content {
      background: white; padding: 20px; border-radius: 10px;
      width: 90%; max-width: 520px; box-shadow: 0 0 10px #000;
      position: relative; text-align: left;
    }
    .popup-content h3 { margin-top: 0; }
    .close-btn { position: absolute; top: 10px; right: 15px; font-size: 20px; cursor: pointer; color: #555; }
    .icon { font-size: 20px; margin-right: 8px; }
    .popup-list { margin: 8px 0 0 0; padding-left: 18px; }
  </style>
</head>
<body>

  <h2>%%HEADER_TITLE%%</h2>

  <div class="calendar-nav">
    <button id="prevBtn" title="" aria-label="prev">&#8592;</button>
    <button id="todayBtn" title="" aria-label="today">📍</button>
    <span id="monthYear"></span>
    <button id="nextBtn" title="" aria-label="next">&#8594;</button>
  </div>

  <table id="calendar">
    <thead><tr id="dowRow"></tr></thead>
    <tbody></tbody>
  </table>

  <div class="footer-info">
    <p><strong><span id="nextClassLabel"></span></strong> <span id="nextClass">...</span></p>
    <p><strong><span id="nextTaskLabel"></span></strong> <span id="nextTask">...</span></p>
  </div>

  <div id="popupOverlay" class="popup-overlay">
    <div class="popup-content">
      <span class="close-btn" onclick="closePopup()">❌</span>
      <h3><span id="popupIcon" class="icon">📌</span><span id="popupTitle"></span></h3>
      <p><strong><span id="popupDateLabel"></span></strong> <span id="popupDate"></span></p>
      <div id="popupBody"></div>
    </div>
  </div>

  <script>
    const year = %%YEAR%%;
    const allowedMonths = %%ALLOWED_MONTHS%%;
    const EXPORT_LANG = "%%EXPORT_LANG%%";

    const I18N = {
      es: {
        locale: "es-MX",
        title: "%%DOC_TITLE%%",
        prevTitle: "Mes anterior",
        nextTitle: "Mes siguiente",
        todayTitle: "Ir a hoy",
        dow: ["Dom","Lun","Mar","Mié","Jue","Vie","Sáb"],
        nextClassLabel: "Próxima clase:",
        nextTaskLabel: "Próxima tarea:",
        noneUpcomingClass: "No hay próximas clases",
        noneUpcomingTask: "No hay próximas tareas",
        popupTitle: "Eventos",
        dateLabel: "Fecha:",
        outOfRange: "Hoy está fuera del rango permitido.",
        todayTag: "HOY"
      },
      en: {
        locale: "en-US",
        title: "%%DOC_TITLE%%",
        prevTitle: "Previous month",
        nextTitle: "Next month",
        todayTitle: "Go to today",
        dow: ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"],
        nextClassLabel: "Next class:",
        nextTaskLabel: "Next task:",
        noneUpcomingClass: "No upcoming classes",
        noneUpcomingTask: "No upcoming tasks",
        popupTitle: "Events",
        dateLabel: "Date:",
        outOfRange: "Today is outside the allowed calendar range.",
        todayTag: "TODAY"
      }
    };

    const T = I18N[EXPORT_LANG] || I18N.en;

    const EVENTS = %%EVENTS_JSON%%;

    const TYPE_TO_META = {
      "Class": { css: "class-day", icon: "📘" },
      "Task":  { css: "task-day",  icon: "📎" },
      "Info":  { css: "info-day",  icon: "🗓️" },
      "Exam":  { css: "exam-day",  icon: "📝" },
    };

    function eventsByDate(events) {
      const map = {};
      for (const ev of events) {
        if (!map[ev.date]) map[ev.date] = [];
        map[ev.date].push(ev);
      }
      const order = { "Exam": 0, "Task": 1, "Class": 2, "Info": 3 };
      for (const k of Object.keys(map)) {
        map[k].sort((a,b) => (order[a.type] ?? 99) - (order[b.type] ?? 99));
      }
      return map;
    }

    const EVENTS_BY_DATE = eventsByDate(EVENTS);

    let currentMonthIndex = 0;
    const calendarBody = document.querySelector("#calendar tbody");
    const monthYearEl = document.getElementById("monthYear");

    document.title = T.title;
    document.getElementById("prevBtn").title = T.prevTitle;
    document.getElementById("nextBtn").title = T.nextTitle;
    document.getElementById("todayBtn").title = T.todayTitle;
    document.getElementById("nextClassLabel").textContent = T.nextClassLabel;
    document.getElementById("nextTaskLabel").textContent = T.nextTaskLabel;
    document.getElementById("popupTitle").textContent = T.popupTitle;
    document.getElementById("popupDateLabel").textContent = T.dateLabel;

    const dowRow = document.getElementById("dowRow");
    dowRow.innerHTML = T.dow.map(d => `<th>${d}</th>`).join("");

    document.getElementById("prevBtn").addEventListener("click", () => changeMonth(-1));
    document.getElementById("nextBtn").addEventListener("click", () => changeMonth(1));
    document.getElementById("todayBtn").addEventListener("click", goToToday);

    function renderCalendar(month) {
      const firstDay = new Date(year, month, 1);
      const lastDay = new Date(year, month + 1, 0);
      const startDay = firstDay.getDay();

      const monthName = firstDay.toLocaleString(T.locale, { month: 'long' }).toUpperCase();
      monthYearEl.textContent = `${monthName} ${year}`;
      calendarBody.innerHTML = "";

      const now = new Date();
      const todayKey = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;

      let row = document.createElement("tr");
      let dayCounter = 1;

      for (let i = 0; i < 42; i++) {
        const cell = document.createElement("td");

        if (i >= startDay && dayCounter <= lastDay.getDate()) {
          const dateKey = `${year}-${String(month + 1).padStart(2,'0')}-${String(dayCounter).padStart(2,'0')}`;
          cell.textContent = dayCounter;

          if (dateKey === todayKey) {
            cell.classList.add("today");
            const tag = document.createElement("div");
            tag.className = "today-marker";
            tag.textContent = T.todayTag;
            cell.appendChild(tag);
          }

          const list = EVENTS_BY_DATE[dateKey] || [];
          if (list.length > 0) {
            for (const ev of list) {
              const meta = TYPE_TO_META[ev.type];
              if (meta) cell.classList.add(meta.css);
            }
            cell.title = list.map(ev => `${ev.type}: ${ev.title}`).join(" | ");
            cell.style.cursor = "pointer";
            cell.addEventListener("click", () => showPopup(dateKey));
          }

          dayCounter++;
        } else {
          cell.innerHTML = "&nbsp;";
        }

        row.appendChild(cell);
        if ((i + 1) % 7 === 0) {
          calendarBody.appendChild(row);
          row = document.createElement("tr");
        }
      }

      updateNextEvents();
    }

    function formatDate(dateStr) {
      const [y, m, d] = dateStr.split("-");
      const dt = new Date(y, m - 1, d);
      return dt.toLocaleDateString(T.locale, { day: 'numeric', month: 'long', year: 'numeric' });
    }

    function showPopup(dateStr) {
      document.getElementById("popupDate").textContent = formatDate(dateStr);

      const list = EVENTS_BY_DATE[dateStr] || [];
      const body = document.getElementById("popupBody");

      if (list.length === 0) {
        body.innerHTML = "<p>No events</p>";
      } else {
        const items = list.map(ev => {
          const meta = TYPE_TO_META[ev.type] || { icon: "📌" };
          return `<li>${meta.icon} <strong>${ev.type}:</strong> ${ev.title}</li>`;
        }).join("");
        body.innerHTML = `<ul class="popup-list">${items}</ul>`;
      }

      document.getElementById("popupOverlay").style.display = "flex";
    }

    function closePopup() {
      document.getElementById("popupOverlay").style.display = "none";
    }

    function changeMonth(direction) {
      currentMonthIndex += direction;
      if (currentMonthIndex < 0) currentMonthIndex = 0;
      if (currentMonthIndex >= allowedMonths.length) currentMonthIndex = allowedMonths.length - 1;
      renderCalendar(allowedMonths[currentMonthIndex]);
      closePopup();
    }

    function goToToday() {
      const now = new Date();
      const idx = allowedMonths.indexOf(now.getMonth());
      if (idx !== -1) {
        currentMonthIndex = idx;
        renderCalendar(allowedMonths[currentMonthIndex]);
        closePopup();
      } else {
        alert(T.outOfRange);
      }
    }

    function updateNextEvents() {
      const now = new Date();
      const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

      function findNext(type) {
        return EVENTS
          .filter(ev => ev.type === type)
          .filter(ev => new Date(ev.date) >= today)
          .sort((a, b) => a.date.localeCompare(b.date))[0];
      }

      const nextClass = findNext("Class");
      const nextTask = findNext("Task");

      document.getElementById("nextClass").textContent = nextClass
        ? `${formatDate(nextClass.date)} - ${nextClass.title}`
        : T.noneUpcomingClass;

      document.getElementById("nextTask").textContent = nextTask
        ? `${formatDate(nextTask.date)} - ${nextTask.title}`
        : T.noneUpcomingTask;
    }

    renderCalendar(allowedMonths[currentMonthIndex]);
  </script>

</body>
</html>
"""

# =========================
# (NUEVO) PDF helper: wrap
# =========================

def _wrap_lines(text: str, max_width: float, font_name: str, font_size: int):
    """
    Envuelve texto a múltiples líneas usando ancho real de fuente (ReportLab).
    Devuelve lista de líneas.
    """
    if not text:
        return []
    if stringWidth is None:
        return [text[:80]]

    words = text.split()
    lines = []
    cur = ""
    for w in words:
        test = (cur + " " + w).strip()
        if stringWidth(test, font_name, font_size) <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines

# =========================
# Popup selector de fecha (mini calendario)
# =========================

class DatePicker(tk.Toplevel):
    """
    Mini-calendario para escoger una fecha.
    - current_date: date inicial para mostrar (mes/año)
    - on_pick(date_obj) callback cuando el usuario selecciona un día
    """
    def __init__(self, master, title: str, current_date: date | None, on_pick, min_date: date | None = None, max_date: date | None = None):
        super().__init__(master)
        self.transient(master)
        self.grab_set()
        self.resizable(False, False)
        self.title(title)

        self.on_pick = on_pick
        self.min_date = min_date
        self.max_date = max_date

        base = current_date or date.today()
        self.view_year = base.year
        self.view_month = base.month

        self.header_var = tk.StringVar()
        self._build_ui()
        self._render()

        self.update_idletasks()
        try:
            x = master.winfo_rootx() + 80
            y = master.winfo_rooty() + 80
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=10)

        ttk.Button(top, text="◀", width=3, command=self._prev_month).pack(side="left")
        ttk.Button(top, text="Hoy", command=self._go_today).pack(side="left", padx=6)
        ttk.Label(top, textvariable=self.header_var, font=("Segoe UI", 11, "bold")).pack(side="left", padx=10)
        ttk.Button(top, text="▶", width=3, command=self._next_month).pack(side="left")

        self.grid = ttk.Frame(self)
        self.grid.pack(fill="both", padx=10, pady=(0, 10))

        days = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"]
        for c, dname in enumerate(days):
            ttk.Label(self.grid, text=dname, anchor="center").grid(row=0, column=c, padx=2, pady=2, sticky="nsew")

        for c in range(7):
            self.grid.columnconfigure(c, weight=1)

        self.buttons = []

    def _render(self):
        self.header_var.set(f"{calendar.month_name[self.view_month].upper()} {self.view_year}")

        for b in self.buttons:
            b.destroy()
        self.buttons.clear()

        cal = calendar.Calendar(firstweekday=6)
        month_days = list(cal.itermonthdates(self.view_year, self.view_month))[:42]
        today = date.today()

        for i, d in enumerate(month_days):
            r = 1 + (i // 7)
            c = i % 7
            in_month = (d.month == self.view_month)

            state = tk.NORMAL
            if not in_month:
                state = tk.DISABLED
            if self.min_date and d < self.min_date:
                state = tk.DISABLED
            if self.max_date and d > self.max_date:
                state = tk.DISABLED

            btn = tk.Button(
                self.grid,
                text=str(d.day),
                width=4,
                state=state,
                command=lambda dd=d: self._pick(dd),
            )

            if d == today and state == tk.NORMAL:
                btn.config(highlightthickness=2, highlightbackground="black")

            if not in_month:
                btn.config(relief="flat")

            btn.grid(row=r, column=c, padx=2, pady=2, sticky="nsew")
            self.buttons.append(btn)

    def _pick(self, d: date):
        self.grab_release()
        self.destroy()
        self.on_pick(d)

    def _prev_month(self):
        if self.view_month == 1:
            self.view_month = 12
            self.view_year -= 1
        else:
            self.view_month -= 1
        self._render()

    def _next_month(self):
        if self.view_month == 12:
            self.view_month = 1
            self.view_year += 1
        else:
            self.view_month += 1
        self._render()

    def _go_today(self):
        t = date.today()
        self.view_year = t.year
        self.view_month = t.month
        self._render()

# =========================
# Persistencia
# =========================

def empty_project_dict():
    return {
        "version": 5,
        "year": None,
        "periodo": None,
        "allowed_months": None,
        "header_title": "",
        "export_lang": "es",
        "view_year": None,
        "view_month": None,
        "selected_date": None,
        "events": [],
        "semester_start": None,
        "semester_end": None,
        "class_weekdays": [True, True, True, True, True],  # Mon..Fri
        "default_class_title": "CLASE",

        # NUEVO: rangos
        "exam_ranges": [],         # [{start, end, label}]
        "cutoff_ranges": [],       # fin de actividades/tareas (Info)
        "holiday_ranges": [],      # vacaciones (Info)
    }

# =========================
# App Tkinter
# =========================

class CalendarBuilderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.geometry("1380x860")

        self.events: list[Event] = []
        self.clipboard_events: list[Event] = []
        self.current_project_path: str | None = None

        # RANGOS (lista de dicts con start/end/label)
        self.exam_ranges: list[dict] = []
        self.cutoff_ranges: list[dict] = []
        self.holiday_ranges: list[dict] = []

        today = date.today()
        self.year_var = tk.IntVar(value=today.year)

        self.periodo_var = tk.StringVar(value="Primavera (Ene–May)")
        self.allowed_months_var = tk.StringVar(value="0,1,2,3,4")
        self.header_title_var = tk.StringVar(value="")
        self.export_lang_var = tk.StringVar(value="es")

        # Semester setup
        self.sem_start_var = tk.StringVar(value=f"{today.year:04d}-01-01")
        self.sem_end_var   = tk.StringVar(value=f"{today.year:04d}-05-31")
        self.default_class_title_var = tk.StringVar(value="CLASE")

        # Weekdays Mon..Fri
        self.class_days_vars = [tk.BooleanVar(value=True) for _ in range(5)]

        # View state
        self.view_year = today.year
        self.view_month = today.month
        self.selected_date_str = tk.StringVar(value=self._date_str(today))

        # New event manual
        self.new_type_var = tk.StringVar(value="Class")
        self.new_title_var = tk.StringVar(value="")

        # Status
        self.status_var = tk.StringVar(value="Listo")

        self._build_ui()
        self._apply_periodo_to_months()
        self._render_month()
        self.select_date(self.selected_date_str.get())
        self._update_titlebar()
        self._refresh_holidays_list()
        self._refresh_ranges_lists()

    # ---------- Helpers ----------
    def _date_str(self, d: date) -> str:
        return f"{d.year:04d}-{d.month:02d}-{d.day:02d}"

    def _parse_date(self, s: str) -> date | None:
        s = (s or "").strip()
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            return None

    def _parse_allowed_months(self, raw: str):
        raw = (raw or "").strip()
        if not raw:
            return []
        out = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                m = int(part)
                if 0 <= m <= 11:
                    out.append(m)
            except ValueError:
                pass
        unique = []
        for m in out:
            if m not in unique:
                unique.append(m)
        return unique

    def _events_on_date(self, date_str: str):
        return [e for e in self.events if e.date_str == date_str]

    def _refresh_events_list(self):
        self.events_listbox.delete(0, tk.END)
        items = self._events_on_date(self.selected_date_str.get())
        for ev in items:
            self.events_listbox.insert(tk.END, f"{ev.type}: {ev.title}")

        self.edit_type_var.set("")
        self.edit_title_var.set("")
        self.edit_index = None

    def _update_titlebar(self):
        base = "Generador de Calendario del Curso"
        if self.current_project_path:
            self.title(f"{base} — {Path(self.current_project_path).name}")
        else:
            self.title(f"{base} — (sin guardar)")

    def _is_holiday(self, date_str: str) -> bool:
        for e in self._events_on_date(date_str):
            if e.type == "Info" and ("[FESTIVO]" in e.title or "[VACACIONES]" in e.title):
                return True
        return False

    def _holidays(self) -> list[Event]:
        return sorted(
            [e for e in self.events if e.type == "Info" and ("[FESTIVO]" in e.title or "[VACACIONES]" in e.title)],
            key=lambda e: e.date_str
        )

    def _refresh_holidays_list(self):
        self.holidays_listbox.delete(0, tk.END)
        for e in self._holidays():
            pretty = e.title.replace("[FESTIVO] ", "").replace("[VACACIONES] ", "")
            tag = "VAC" if "[VACACIONES]" in e.title else "FES"
            self.holidays_listbox.insert(tk.END, f"{e.date_str} — [{tag}] {pretty}")

    def _refresh_ranges_lists(self):
        self.exam_ranges_listbox.delete(0, tk.END)
        for r in self.exam_ranges:
            self.exam_ranges_listbox.insert(tk.END, f"{r['start']} → {r['end']}  |  {r['label']}")

        self.cutoff_ranges_listbox.delete(0, tk.END)
        for r in self.cutoff_ranges:
            self.cutoff_ranges_listbox.insert(tk.END, f"{r['start']} → {r['end']}  |  {r['label']}")

        self.holiday_ranges_listbox.delete(0, tk.END)
        for r in self.holiday_ranges:
            self.holiday_ranges_listbox.insert(tk.END, f"{r['start']} → {r['end']}  |  {r['label']}")

    def _set_status(self, msg: str):
        self.status_var.set(msg)

    def _dates_in_range(self, start: date, end: date):
        cur = start
        while cur <= end:
            yield cur
            cur += timedelta(days=1)

    def _has_any_event_on_date(self, date_str: str) -> bool:
        return len(self._events_on_date(date_str)) > 0

    # ---------- DatePicker actions (simple dates) ----------
    def pick_semester_start(self):
        cur = self._parse_date(self.sem_start_var.get()) or date.today()
        DatePicker(self, "Seleccionar INICIO del semestre", cur, self._on_pick_start)

    def _on_pick_start(self, d: date):
        self.sem_start_var.set(self._date_str(d))
        self._set_status(f"Inicio del semestre: {self.sem_start_var.get()}")

    def pick_semester_end(self):
        cur = self._parse_date(self.sem_end_var.get()) or date.today()
        DatePicker(self, "Seleccionar FIN del semestre", cur, self._on_pick_end)

    def _on_pick_end(self, d: date):
        self.sem_end_var.set(self._date_str(d))
        self._set_status(f"Fin del semestre: {self.sem_end_var.get()}")

    def pick_holiday_single(self):
        cur = date.today()
        DatePicker(self, "Agregar FESTIVO (un día)", cur, self._on_pick_holiday_single)

    def _on_pick_holiday_single(self, d: date):
        ds = self._date_str(d)
        name = simpledialog.askstring("Festivo", f"Nombre del festivo para {ds}:", parent=self)
        if name is None:
            return
        name = name.strip() or "Festivo"

        for e in self.events:
            if e.type == "Info" and e.date_str == ds and "[FESTIVO]" in e.title:
                messagebox.showinfo("Ya existe", "Ese festivo ya existe.")
                self.select_date(ds)
                self._render_month()
                return

        self.events.append(Event(ds, "Info", f"[FESTIVO] {name}"))
        self._refresh_holidays_list()
        self.select_date(ds)
        self._render_month()
        self._set_status(f"Festivo agregado: {ds}")

    # ---------- Range picking (start/end) ----------
    def _pick_range(self, kind: str):
        """
        kind: "exam" | "cutoff" | "vac"
        """
        cur = date.today()
        self._range_kind = kind
        self._range_start = None

        title = {
            "exam": "Seleccionar INICIO del período de EXÁMENES",
            "cutoff": "Seleccionar INICIO del FIN de actividades/tareas",
            "vac": "Seleccionar INICIO de VACACIONES",
        }[kind]

        DatePicker(self, title, cur, self._on_pick_range_start)

    def _on_pick_range_start(self, d: date):
        self._range_start = d
        kind = self._range_kind
        title = {
            "exam": "Seleccionar FIN del período de EXÁMENES",
            "cutoff": "Seleccionar FIN del FIN de actividades/tareas",
            "vac": "Seleccionar FIN de VACACIONES",
        }[kind]
        DatePicker(self, title, d, self._on_pick_range_end, min_date=d)

    def _on_pick_range_end(self, d_end: date):
        start = self._range_start
        end = d_end
        kind = self._range_kind
        if not start or end < start:
            messagebox.showerror("Error", "Rango inválido.")
            return

        # límites solicitados
        if kind == "exam" and len(self.exam_ranges) >= 2:
            messagebox.showerror("Límite", "Ya tienes 2 períodos de exámenes. Elimina uno para agregar otro.")
            return
        if kind == "cutoff" and len(self.cutoff_ranges) >= 4:
            messagebox.showerror("Límite", "Ya tienes 4 períodos de fin de actividades/tareas. Elimina uno para agregar otro.")
            return

        default_label = {
            "exam": f"PERIODO EXÁMENES {len(self.exam_ranges)+1}",
            "cutoff": f"FIN ACT/TAREAS {len(self.cutoff_ranges)+1}",
            "vac": "VACACIONES",
        }[kind]

        label = simpledialog.askstring("Etiqueta", f"Etiqueta para el rango ({self._date_str(start)} → {self._date_str(end)}):",
                                       initialvalue=default_label, parent=self)
        if label is None:
            return
        label = label.strip() or default_label

        # Crear eventos por día
        created = 0
        collisions = 0

        if kind == "exam":
            ev_type = "Exam"
            title = label
        elif kind == "cutoff":
            ev_type = "Info"
            title = f"[CIERRE] {label}"
        else:
            ev_type = "Info"
            title = f"[VACACIONES] {label}"

        # Advertir choques si hay eventos existentes en cualquier fecha del rango
        for dd in self._dates_in_range(start, end):
            ds = self._date_str(dd)
            if self._has_any_event_on_date(ds):
                collisions += 1

        if collisions > 0:
            if not messagebox.askyesno("Choques detectados",
                                       f"Hay {collisions} día(s) del rango que ya tienen eventos.\n¿Crear el rango de todos modos?"):
                return

        existing_set = set((e.date_str, e.type, e.title) for e in self.events)
        for dd in self._dates_in_range(start, end):
            ds = self._date_str(dd)
            key = (ds, ev_type, title)
            if key in existing_set:
                continue
            self.events.append(Event(ds, ev_type, title))
            existing_set.add(key)
            created += 1

        # Guardar rango
        range_obj = {"start": self._date_str(start), "end": self._date_str(end), "label": label}
        if kind == "exam":
            self.exam_ranges.append(range_obj)
        elif kind == "cutoff":
            self.cutoff_ranges.append(range_obj)
        else:
            self.holiday_ranges.append(range_obj)

        self._refresh_ranges_lists()
        self._refresh_holidays_list()
        self._render_month()
        self._refresh_events_list()

        messagebox.showinfo("Rango creado", f"Eventos generados: {created}\nRango: {range_obj['start']} → {range_obj['end']}")
        self._set_status("Rango agregado")

    def _remove_range(self, kind: str):
        """
        Elimina el rango seleccionado y borra los eventos que generó.
        """
        if kind == "exam":
            lb = self.exam_ranges_listbox
            ranges = self.exam_ranges
            ev_type = "Exam"
            title_builder = lambda label: label
        elif kind == "cutoff":
            lb = self.cutoff_ranges_listbox
            ranges = self.cutoff_ranges
            ev_type = "Info"
            title_builder = lambda label: f"[CIERRE] {label}"
        else:
            lb = self.holiday_ranges_listbox
            ranges = self.holiday_ranges
            ev_type = "Info"
            title_builder = lambda label: f"[VACACIONES] {label}"

        sel = lb.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx >= len(ranges):
            return

        r = ranges[idx]
        start = self._parse_date(r["start"])
        end = self._parse_date(r["end"])
        label = r["label"]
        if not start or not end:
            return

        if not messagebox.askyesno("Confirmar", f"¿Eliminar este rango y sus eventos?\n{r['start']} → {r['end']}\n{label}"):
            return

        title = title_builder(label)
        before = len(self.events)
        self.events = [e for e in self.events if not (e.type == ev_type and e.title == title and start <= self._parse_date(e.date_str) <= end)]
        removed = before - len(self.events)

        del ranges[idx]

        self._refresh_ranges_lists()
        self._refresh_holidays_list()
        self._render_month()
        self._refresh_events_list()
        messagebox.showinfo("Listo", f"Rango eliminado.\nEventos borrados: {removed}")

    # ---------- UI ----------
    def _build_ui(self):
        menubar = tk.Menu(self)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Nuevo", command=self.new_project)
        filemenu.add_command(label="Abrir…", command=self.open_project)
        filemenu.add_separator()
        filemenu.add_command(label="Guardar", command=self.save_project)
        filemenu.add_command(label="Guardar como…", command=self.save_project_as)
        filemenu.add_separator()
        filemenu.add_command(label="Exportar HTML…", command=self.export_html)
        filemenu.add_command(label="Exportar PDF…", command=self.export_pdf)  # (NUEVO)
        filemenu.add_separator()
        filemenu.add_command(label="Salir", command=self.quit)
        menubar.add_cascade(label="Archivo", menu=filemenu)
        self.config(menu=menubar)

        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=8)

        ttk.Label(top, text="Año:").pack(side="left")
        ttk.Entry(top, width=6, textvariable=self.year_var).pack(side="left", padx=(4, 12))

        ttk.Label(top, text="Periodo:").pack(side="left")
        periodo_cb = ttk.Combobox(
            top,
            textvariable=self.periodo_var,
            state="readonly",
            width=20,
            values=["Primavera (Ene–May)", "Verano (Jun–Jul)", "Otoño (Ago–Dic)", "Personalizado"],
        )
        periodo_cb.pack(side="left", padx=(4, 12))
        periodo_cb.bind("<<ComboboxSelected>>", lambda e: self._apply_periodo_to_months())

        ttk.Label(top, text="Meses permitidos (0-11):").pack(side="left")
        self.allowed_entry = ttk.Entry(top, width=16, textvariable=self.allowed_months_var, state="disabled")
        self.allowed_entry.pack(side="left", padx=(4, 12))

        ttk.Label(top, text="Encabezado:").pack(side="left")
        ttk.Entry(top, width=24, textvariable=self.header_title_var).pack(side="left", padx=(4, 12))

        ttk.Label(top, text="Exportar HTML:").pack(side="left")
        ttk.Radiobutton(top, text="ES", value="es", variable=self.export_lang_var).pack(side="left", padx=(4, 0))
        ttk.Radiobutton(top, text="EN", value="en", variable=self.export_lang_var).pack(side="left", padx=(4, 12))

        ttk.Button(top, text="Exportar HTML", command=self.export_html).pack(side="right")
        ttk.Button(top, text="Guardar avances", command=self.save_project).pack(side="right", padx=(0, 8))

        # ============ Semestre / Festivos / Días de clase / RANGOS ============
        sem = ttk.LabelFrame(self, text="Semestre / Festivos / Días de clase / Rangos")
        sem.pack(fill="x", padx=10, pady=(0, 10))

        rowA = ttk.Frame(sem); rowA.pack(fill="x", padx=10, pady=6)
        ttk.Label(rowA, text="Inicio:").pack(side="left")
        ttk.Entry(rowA, width=12, textvariable=self.sem_start_var).pack(side="left", padx=(6, 10))
        ttk.Button(rowA, text="Elegir inicio…", command=self.pick_semester_start).pack(side="left")

        ttk.Label(rowA, text="Fin:").pack(side="left", padx=(14, 0))
        ttk.Entry(rowA, width=12, textvariable=self.sem_end_var).pack(side="left", padx=(6, 10))
        ttk.Button(rowA, text="Elegir fin…", command=self.pick_semester_end).pack(side="left")

        ttk.Label(rowA, text="Título por defecto (Class):").pack(side="left", padx=(14, 0))
        ttk.Entry(rowA, width=18, textvariable=self.default_class_title_var).pack(side="left", padx=(6, 14))

        ttk.Button(rowA, text="Generar clases", command=self.generate_classes).pack(side="left", padx=(6, 6))
        ttk.Button(rowA, text="Borrar clases generadas", command=self.clear_generated_classes).pack(side="left")

        rowB = ttk.Frame(sem); rowB.pack(fill="x", padx=10, pady=(0, 10))

        # Días de clase
        days_box = ttk.LabelFrame(rowB, text="Días de clase (L–V)")
        days_box.pack(side="left", fill="y", padx=(0, 10))

        day_names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
        for i, name in enumerate(day_names):
            ttk.Checkbutton(days_box, text=name, variable=self.class_days_vars[i]).pack(anchor="w", padx=10, pady=2)

        # Festivos (single day)
        hol_box = ttk.LabelFrame(rowB, text="Festivos (un día) y Vacaciones (rango)")
        hol_box.pack(side="left", fill="both", expand=True, padx=(0, 10))

        hol_top = ttk.Frame(hol_box); hol_top.pack(fill="x", padx=10, pady=6)
        ttk.Button(hol_top, text="Agregar festivo (un día)…", command=self.pick_holiday_single).pack(side="left")
        ttk.Button(hol_top, text="Agregar vacaciones (rango)…", command=lambda: self._pick_range("vac")).pack(side="left", padx=8)
        ttk.Button(hol_top, text="Eliminar festivo seleccionado", command=self.delete_selected_holiday).pack(side="left", padx=8)

        self.holidays_listbox = tk.Listbox(hol_box, height=6)
        self.holidays_listbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # RANGOS: Exámenes + Cierres + Vacaciones
        ranges_box = ttk.LabelFrame(rowB, text="Rangos")
        ranges_box.pack(side="left", fill="both", expand=True)

        # Exámenes (2)
        ex_frame = ttk.LabelFrame(ranges_box, text="Períodos de exámenes (2)")
        ex_frame.pack(fill="both", expand=True, padx=10, pady=(8, 6))
        ex_btns = ttk.Frame(ex_frame); ex_btns.pack(fill="x", pady=(0, 6))
        ttk.Button(ex_btns, text="Agregar rango…", command=lambda: self._pick_range("exam")).pack(side="left")
        ttk.Button(ex_btns, text="Eliminar rango", command=lambda: self._remove_range("exam")).pack(side="left", padx=8)
        self.exam_ranges_listbox = tk.Listbox(ex_frame, height=3)
        self.exam_ranges_listbox.pack(fill="both", expand=True)

        # Cierres (4)
        co_frame = ttk.LabelFrame(ranges_box, text="Fin de actividades y tareas (4)")
        co_frame.pack(fill="both", expand=True, padx=10, pady=6)
        co_btns = ttk.Frame(co_frame); co_btns.pack(fill="x", pady=(0, 6))
        ttk.Button(co_btns, text="Agregar rango…", command=lambda: self._pick_range("cutoff")).pack(side="left")
        ttk.Button(co_btns, text="Eliminar rango", command=lambda: self._remove_range("cutoff")).pack(side="left", padx=8)
        self.cutoff_ranges_listbox = tk.Listbox(co_frame, height=4)
        self.cutoff_ranges_listbox.pack(fill="both", expand=True)

        # Vacaciones (rango) lista separada (por claridad)
        va_frame = ttk.LabelFrame(ranges_box, text="Vacaciones / festivos por rango")
        va_frame.pack(fill="both", expand=True, padx=10, pady=(6, 10))
        va_btns = ttk.Frame(va_frame); va_btns.pack(fill="x", pady=(0, 6))
        ttk.Button(va_btns, text="Agregar rango…", command=lambda: self._pick_range("vac")).pack(side="left")
        ttk.Button(va_btns, text="Eliminar rango", command=lambda: self._remove_range("vac")).pack(side="left", padx=8)
        self.holiday_ranges_listbox = tk.Listbox(va_frame, height=3)
        self.holiday_ranges_listbox.pack(fill="both", expand=True)

        # =================== Main layout ===================
        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        left = ttk.Frame(main)
        left.pack(side="left", fill="both", expand=True)

        right = ttk.Frame(main)
        right.pack(side="right", fill="y")

        cal_ctrl = ttk.Frame(left)
        cal_ctrl.pack(fill="x", pady=(0, 6))
        ttk.Button(cal_ctrl, text="◀ Mes anterior", command=self.prev_month).pack(side="left")
        ttk.Button(cal_ctrl, text="Ir a hoy", command=self.go_to_today).pack(side="left", padx=6)
        ttk.Button(cal_ctrl, text="Mes siguiente ▶", command=self.next_month).pack(side="left", padx=6)

        self.month_label = ttk.Label(cal_ctrl, text="", font=("Segoe UI", 11, "bold"))
        self.month_label.pack(side="left", padx=12)

        self.cal_frame = ttk.Frame(left)
        self.cal_frame.pack(fill="both", expand=True)

        days = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"]
        for c, dname in enumerate(days):
            lbl = ttk.Label(self.cal_frame, text=dname, anchor="center")
            lbl.grid(row=0, column=c, sticky="nsew", padx=1, pady=1)
        for c in range(7):
            self.cal_frame.columnconfigure(c, weight=1)
        for r in range(1, 7):
            self.cal_frame.rowconfigure(r, weight=1)

        # Panel derecho: selección y lista
        sel = ttk.LabelFrame(right, text="Fecha seleccionada")
        sel.pack(fill="x", padx=8, pady=6)
        ttk.Label(sel, textvariable=self.selected_date_str, font=("Segoe UI", 10, "bold")).pack(padx=8, pady=8)

        lst = ttk.LabelFrame(right, text="Eventos en la fecha")
        lst.pack(fill="both", expand=True, padx=8, pady=6)

        self.events_listbox = tk.Listbox(lst, height=10)
        self.events_listbox.pack(fill="both", expand=True, padx=8, pady=(8, 6))
        self.events_listbox.bind("<<ListboxSelect>>", self.on_select_event)

        btns = ttk.Frame(lst)
        btns.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(btns, text="Eliminar", command=self.delete_selected_event).pack(side="left")
        ttk.Button(btns, text="Copiar", command=self.copy_selected_event).pack(side="left", padx=6)
        ttk.Button(btns, text="Pegar", command=self.paste_events_to_selected_date).pack(side="left")

        # Editor de evento existente
        edit = ttk.LabelFrame(right, text="Editar evento seleccionado")
        edit.pack(fill="x", padx=8, pady=6)

        self.edit_type_var = tk.StringVar(value="")
        self.edit_title_var = tk.StringVar(value="")
        self.edit_index = None

        er1 = ttk.Frame(edit); er1.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(er1, text="Tipo:").pack(side="left")
        ttk.Combobox(er1, textvariable=self.edit_type_var, values=EVENT_TYPES, state="readonly", width=10)\
            .pack(side="left", padx=6)

        er2 = ttk.Frame(edit); er2.pack(fill="x", padx=8, pady=4)
        ttk.Label(er2, text="Título:").pack(side="left")
        ttk.Entry(er2, textvariable=self.edit_title_var, width=36).pack(side="left", padx=6)

        er3 = ttk.Frame(edit); er3.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(er3, text="Guardar cambios", command=self.save_event_edits).pack(side="left")
        ttk.Button(er3, text="Cancelar edición", command=self.cancel_event_edit).pack(side="left", padx=8)

        # Nuevo evento manual
        add = ttk.LabelFrame(right, text="Nuevo evento manual")
        add.pack(fill="x", padx=8, pady=6)

        row1 = ttk.Frame(add); row1.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(row1, text="Tipo:").pack(side="left")
        ttk.Combobox(row1, textvariable=self.new_type_var, values=EVENT_TYPES, state="readonly", width=10)\
            .pack(side="left", padx=6)

        row2 = ttk.Frame(add); row2.pack(fill="x", padx=8, pady=4)
        ttk.Label(row2, text="Título:").pack(side="left")
        ttk.Entry(row2, textvariable=self.new_title_var, width=36).pack(side="left", padx=6)

        row3 = ttk.Frame(add); row3.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(row3, text="Agregar evento", command=self.add_event).pack(side="left")

        status = ttk.Label(self, textvariable=self.status_var, anchor="w")
        status.pack(fill="x", padx=10, pady=(0, 8))

    # ---------- Periodo -> allowedMonths ----------
    def _apply_periodo_to_months(self):
        periodo = self.periodo_var.get().strip()
        y = int(self.year_var.get())
        if periodo.startswith("Primavera"):
            self.allowed_months_var.set("0,1,2,3,4")
            self.allowed_entry.configure(state="disabled")
            self.sem_start_var.set(f"{y:04d}-01-01")
            self.sem_end_var.set(f"{y:04d}-05-31")
        elif periodo.startswith("Verano"):
            self.allowed_months_var.set("5,6")
            self.allowed_entry.configure(state="disabled")
            self.sem_start_var.set(f"{y:04d}-06-01")
            self.sem_end_var.set(f"{y:04d}-07-31")
        elif periodo.startswith("Otoño"):
            self.allowed_months_var.set("7,8,9,10,11")
            self.allowed_entry.configure(state="disabled")
            self.sem_start_var.set(f"{y:04d}-08-01")
            self.sem_end_var.set(f"{y:04d}-12-31")
        else:
            if not self.allowed_months_var.get().strip():
                self.allowed_months_var.set("0,1,2")
            self.allowed_entry.configure(state="normal")

    # ---------- Calendar rendering ----------
    def _render_month(self):
        y = self.view_year
        m = self.view_month
        self.month_label.config(text=f"{calendar.month_name[m].upper()} {y}")

        for widget in self.cal_frame.winfo_children():
            info = widget.grid_info()
            if info and int(info.get("row", 0)) >= 1:
                widget.destroy()

        cal = calendar.Calendar(firstweekday=6)
        month_days = list(cal.itermonthdates(y, m))
        today_str = self._date_str(date.today())

        for i, d in enumerate(month_days[:42]):
            r = 1 + (i // 7)
            c = i % 7
            in_month = (d.month == m)
            d_str = self._date_str(d)

            evs = self._events_on_date(d_str)
            has_events = len(evs) > 0

            text = str(d.day)
            if self._is_holiday(d_str):
                text += "\n[F]"
            if has_events:
                text += f"\n({len(evs)})"

            btn = tk.Button(
                self.cal_frame,
                text=text,
                relief="raised" if in_month else "flat",
                fg="black" if in_month else "#999999",
                command=lambda ds=d_str: self.on_day_click(ds),
                wraplength=70,
                justify="center",
            )
            if d_str == today_str:
                btn.config(highlightthickness=2, highlightbackground="black")

            # gris si hay eventos
            if has_events:
                btn.config(bg="#e6e6e6")

            # azul si es festivo/vacaciones
            if self._is_holiday(d_str):
                btn.config(bg="#d9edf7")

            btn.grid(row=r, column=c, sticky="nsew", padx=1, pady=1)

    def on_day_click(self, date_str: str):
        self.select_date(date_str)

    # ---------- Navigation ----------
    def prev_month(self):
        if self.view_month == 1:
            self.view_month = 12
            self.view_year -= 1
        else:
            self.view_month -= 1
        self._render_month()

    def next_month(self):
        if self.view_month == 12:
            self.view_month = 1
            self.view_year += 1
        else:
            self.view_month += 1
        self._render_month()

    def go_to_today(self):
        t = date.today()
        self.view_year = t.year
        self.view_month = t.month
        self.select_date(self._date_str(t))
        self._render_month()

    # ---------- Selection & CRUD ----------
    def select_date(self, date_str: str):
        self.selected_date_str.set(date_str)
        self._refresh_events_list()

    def add_event(self):
        d = self.selected_date_str.get()
        t = self.new_type_var.get().strip()
        title = self.new_title_var.get().strip()

        if t not in EVENT_TYPES:
            messagebox.showerror("Error", "Tipo inválido.")
            return
        if not title:
            messagebox.showerror("Error", "El título no puede estar vacío.")
            return

        if self._events_on_date(d):
            if not messagebox.askyesno("Choque detectado", f"Ya existen eventos en {d}.\n¿Agregar de todos modos?"):
                return

        self.events.append(Event(d, t, title))
        self.new_title_var.set("")
        self._refresh_events_list()
        self._render_month()

    def delete_selected_event(self):
        sel = self.events_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        d = self.selected_date_str.get()
        items = self._events_on_date(d)
        if idx >= len(items):
            return
        removed = items[idx]
        self.events.remove(removed)
        self._refresh_events_list()
        self._refresh_holidays_list()
        self._render_month()

    def copy_selected_event(self):
        sel = self.events_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        d = self.selected_date_str.get()
        items = self._events_on_date(d)
        if idx >= len(items):
            return
        ev = items[idx]
        self.clipboard_events = [Event(ev.date_str, ev.type, ev.title)]
        messagebox.showinfo("Copiado", "Evento copiado. Selecciona otra fecha y presiona Pegar.")

    def paste_events_to_selected_date(self):
        if not self.clipboard_events:
            return
        target = self.selected_date_str.get()
        if self._events_on_date(target):
            if not messagebox.askyesno("Choque detectado", f"Ya existen eventos en {target}.\n¿Pegar de todos modos?"):
                return
        for ev in self.clipboard_events:
            self.events.append(Event(target, ev.type, ev.title))
        self._refresh_events_list()
        self._refresh_holidays_list()
        self._render_month()

    # ---------- Edit existing event ----------
    def on_select_event(self, _evt=None):
        sel = self.events_listbox.curselection()
        if not sel:
            self.cancel_event_edit()
            return
        idx = sel[0]
        d = self.selected_date_str.get()
        items = self._events_on_date(d)
        if idx >= len(items):
            self.cancel_event_edit()
            return
        ev = items[idx]
        self.edit_index = idx
        self.edit_type_var.set(ev.type)
        self.edit_title_var.set(ev.title)

    def save_event_edits(self):
        if self.edit_index is None:
            return
        d = self.selected_date_str.get()
        items = self._events_on_date(d)
        if self.edit_index >= len(items):
            return
        ev = items[self.edit_index]

        new_type = (self.edit_type_var.get() or "").strip()
        new_title = (self.edit_title_var.get() or "").strip()

        if new_type not in EVENT_TYPES:
            messagebox.showerror("Error", "Tipo inválido.")
            return
        if not new_title:
            messagebox.showerror("Error", "El título no puede estar vacío.")
            return

        ev.type = new_type
        ev.title = new_title

        self._refresh_events_list()
        self._refresh_holidays_list()
        self._render_month()
        messagebox.showinfo("Listo", "Evento actualizado.")

    def cancel_event_edit(self):
        self.edit_index = None
        self.edit_type_var.set("")
        self.edit_title_var.set("")

    # ---------- Holidays list (single-day only removal here) ----------
    def delete_selected_holiday(self):
        sel = self.holidays_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        holidays = self._holidays()
        if idx >= len(holidays):
            return
        ev = holidays[idx]
        # Solo elimina el evento puntual (si es parte de un rango, se elimina desde "Eliminar rango")
        self.events.remove(ev)
        self._refresh_holidays_list()
        self._render_month()
        self._refresh_events_list()

    # ---------- Generate classes ----------
    def generate_classes(self):
        y = int(self.year_var.get())
        start = self._parse_date(self.sem_start_var.get())
        end = self._parse_date(self.sem_end_var.get())
        if not start or not end:
            messagebox.showerror("Error", "Inicio/Fin inválidos. Usa el selector o YYYY-MM-DD.")
            return
        if end < start:
            messagebox.showerror("Error", "La fecha de fin no puede ser anterior al inicio.")
            return

        selected_weekdays = [i for i, v in enumerate(self.class_days_vars) if v.get()]  # Mon=0..Fri=4
        if not selected_weekdays:
            messagebox.showerror("Error", "Selecciona al menos un día de clase (L–V).")
            return

        default_title = (self.default_class_title_var.get() or "CLASE").strip() or "CLASE"
        existing = set((e.date_str, e.type, e.title) for e in self.events)

        added = 0
        skipped_holiday = 0
        skipped_dup = 0

        cur = start
        while cur <= end:
            if cur.weekday() in selected_weekdays:
                ds = self._date_str(cur)
                if self._is_holiday(ds):
                    skipped_holiday += 1
                else:
                    key = (ds, "Class", default_title)
                    if key in existing:
                        skipped_dup += 1
                    else:
                        self.events.append(Event(ds, "Class", default_title))
                        existing.add(key)
                        added += 1
            cur += timedelta(days=1)

        self._render_month()
        self._refresh_events_list()
        messagebox.showinfo(
            "Generación completa",
            f"Clases agregadas: {added}\nOmitidas por festivo/vacaciones: {skipped_holiday}\nOmitidas por duplicado: {skipped_dup}"
        )

    def clear_generated_classes(self):
        default_title = (self.default_class_title_var.get() or "CLASE").strip() or "CLASE"
        if not messagebox.askyesno("Confirmar", f"¿Borrar TODAS las clases con título exacto:\n\n{default_title}\n\n?"):
            return

        before = len(self.events)
        self.events = [e for e in self.events if not (e.type == "Class" and e.title == default_title)]
        removed = before - len(self.events)

        self._render_month()
        self._refresh_events_list()
        messagebox.showinfo("Listo", f"Clases eliminadas: {removed}")

    # =========================
    # Persistencia
    # =========================

    def new_project(self):
        if not messagebox.askyesno("Nuevo proyecto", "¿Crear un nuevo proyecto? (Se perderán cambios no guardados)"):
            return
        today = date.today()
        self.events = []
        self.clipboard_events = []
        self.current_project_path = None

        self.exam_ranges = []
        self.cutoff_ranges = []
        self.holiday_ranges = []

        self.year_var.set(today.year)
        self.periodo_var.set("Primavera (Ene–May)")
        self.allowed_months_var.set("0,1,2,3,4")
        self.header_title_var.set("")
        self.export_lang_var.set("es")

        self.sem_start_var.set(f"{today.year:04d}-01-01")
        self.sem_end_var.set(f"{today.year:04d}-05-31")
        self.default_class_title_var.set("CLASE")
        for v in self.class_days_vars:
            v.set(True)

        self.view_year = today.year
        self.view_month = today.month
        self.selected_date_str.set(self._date_str(today))
        self.new_title_var.set("")
        self.new_type_var.set("Class")

        self._apply_periodo_to_months()
        self._render_month()
        self.select_date(self.selected_date_str.get())
        self._refresh_holidays_list()
        self._refresh_ranges_lists()
        self._update_titlebar()

    def open_project(self):
        path = filedialog.askopenfilename(
            filetypes=[("Proyecto de calendario (*.json)", "*.json"), ("Todos los archivos", "*.*")]
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el archivo:\n{e}")
            return

        try:
            self.year_var.set(int(data.get("year") or date.today().year))
            self.periodo_var.set(data.get("periodo") or "Primavera (Ene–May)")
            self.allowed_months_var.set(data.get("allowed_months") or "0,1,2,3,4")
            self.header_title_var.set(data.get("header_title") or "")
            self.export_lang_var.set((data.get("export_lang") or "es").lower())

            self.view_year = int(data.get("view_year") or self.year_var.get())
            self.view_month = int(data.get("view_month") or date.today().month)
            self.selected_date_str.set(data.get("selected_date") or self._date_str(date.today()))

            self.sem_start_var.set(data.get("semester_start") or f"{self.year_var.get():04d}-01-01")
            self.sem_end_var.set(data.get("semester_end") or f"{self.year_var.get():04d}-05-31")
            self.default_class_title_var.set(data.get("default_class_title") or "CLASE")

            wd = data.get("class_weekdays")
            if isinstance(wd, list) and len(wd) == 5:
                for i in range(5):
                    self.class_days_vars[i].set(bool(wd[i]))
            else:
                for v in self.class_days_vars:
                    v.set(True)

            self.events = []
            for ev in data.get("events", []):
                ds, tp, title = ev.get("date"), ev.get("type"), ev.get("title")
                if isinstance(ds, str) and isinstance(tp, str) and isinstance(title, str) and tp in EVENT_TYPES:
                    self.events.append(Event(ds, tp, title))

            self.exam_ranges = data.get("exam_ranges", []) or []
            self.cutoff_ranges = data.get("cutoff_ranges", []) or []
            self.holiday_ranges = data.get("holiday_ranges", []) or []

            self.clipboard_events = []
            self.current_project_path = path

            self._apply_periodo_to_months()
            self._render_month()
            self.select_date(self.selected_date_str.get())
            self._refresh_holidays_list()
            self._refresh_ranges_lists()
            self._update_titlebar()

            messagebox.showinfo("Proyecto cargado", f"Se cargó el proyecto:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"El archivo no tiene el formato esperado:\n{e}")

    def _project_to_dict(self):
        d = empty_project_dict()
        d["year"] = int(self.year_var.get())
        d["periodo"] = self.periodo_var.get()
        d["allowed_months"] = self.allowed_months_var.get()
        d["header_title"] = self.header_title_var.get()
        d["export_lang"] = self.export_lang_var.get()
        d["view_year"] = int(self.view_year)
        d["view_month"] = int(self.view_month)
        d["selected_date"] = self.selected_date_str.get()
        d["events"] = [{"date": e.date_str, "type": e.type, "title": e.title} for e in self.events]
        d["semester_start"] = self.sem_start_var.get().strip()
        d["semester_end"] = self.sem_end_var.get().strip()
        d["class_weekdays"] = [v.get() for v in self.class_days_vars]
        d["default_class_title"] = (self.default_class_title_var.get() or "CLASE").strip()

        d["exam_ranges"] = self.exam_ranges
        d["cutoff_ranges"] = self.cutoff_ranges
        d["holiday_ranges"] = self.holiday_ranges
        return d

    def save_project(self):
        if self.current_project_path:
            return self._save_project_to_path(self.current_project_path)
        return self.save_project_as()

    def save_project_as(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("Proyecto de calendario (*.json)", "*.json")],
            initialfile="calendario_proyecto.json"
        )
        if not path:
            return
        ok = self._save_project_to_path(path)
        if ok:
            self.current_project_path = path
            self._update_titlebar()

    def _save_project_to_path(self, path: str):
        data = self._project_to_dict()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Guardado", f"Proyecto guardado:\n{path}")
            return True
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar:\n{e}")
            return False

    # =========================
    # Export HTML
    # =========================

    def export_html(self):
        try:
            y = int(self.year_var.get())
        except Exception:
            messagebox.showerror("Error", "Año inválido.")
            return

        allowed = self._parse_allowed_months(self.allowed_months_var.get())
        if not allowed:
            messagebox.showerror("Error", "Meses permitidos vacíos o inválidos. Usa, por ejemplo: 0,1,2")
            return

        export_lang = (self.export_lang_var.get() or "es").strip().lower()
        if export_lang not in ("es", "en"):
            export_lang = "en"

        events_payload = [{"date": e.date_str, "type": e.type, "title": e.title} for e in self.events]
        events_json = json.dumps(events_payload, ensure_ascii=False, indent=2)

        doc_title = "Course Calendar" if export_lang == "en" else "Calendario del Curso"
        html_lang = "en" if export_lang == "en" else "es"
        header_title = self.header_title_var.get()

        html = HTML_TEMPLATE
        html = html.replace("%%HTML_LANG%%", html_lang)
        html = html.replace("%%DOC_TITLE%%", doc_title)
        html = html.replace("%%HEADER_TITLE%%", header_title)
        html = html.replace("%%YEAR%%", str(y))
        html = html.replace("%%ALLOWED_MONTHS%%", json.dumps(allowed))
        html = html.replace("%%EVENTS_JSON%%", events_json)
        html = html.replace("%%EXPORT_LANG%%", export_lang)

        path = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("Archivos HTML", "*.html")],
            initialfile="course_calendar.html"
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
            messagebox.showinfo("Exportado", f"HTML exportado correctamente:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo escribir el HTML:\n{e}")

    # =========================
    # (NUEVO) Export PDF (Ene–May, 1 hoja, layout columnas)
    # =========================

    def _pdf_type_color(self, event_type: str):
        mapping = {
            "Class": rl_colors.HexColor("#ffcc80"),
            "Task":  rl_colors.HexColor("#a5d6a7"),
            "Info":  rl_colors.HexColor("#90caf9"),
            "Exam":  rl_colors.HexColor("#ef9a9a"),
        }
        return mapping.get(event_type, rl_colors.white)

    def _pdf_priority_type_for_date(self, date_str: str) -> str | None:
        order = {"Exam": 0, "Task": 1, "Class": 2, "Info": 3}
        evs = self._events_on_date(date_str)
        if not evs:
            return None
        evs_sorted = sorted(evs, key=lambda e: order.get(e.type, 99))
        return evs_sorted[0].type

    def _pdf_titles_for_date(self, date_str: str) -> list[str]:
        order = {"Exam": 0, "Task": 1, "Class": 2, "Info": 3}
        evs = self._events_on_date(date_str)
        evs_sorted = sorted(evs, key=lambda e: order.get(e.type, 99))
        return [e.title for e in evs_sorted]

    def export_pdf(self):
        if rl_canvas is None:
            messagebox.showerror(
                "PDF no disponible",
                "No se encontró ReportLab.\nInstala con:\n\npip install reportlab"
            )
            return

        try:
            y = int(self.year_var.get())
        except Exception:
            messagebox.showerror("Error", "Año inválido.")
            return

        header_title = (self.header_title_var.get() or "").strip() or "Calendario del Curso"

        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"planner_{y}_ene_may.pdf"
        )
        if not path:
            return

        try:
            self._render_pdf_ene_may(path, y, header_title)
            messagebox.showinfo("Exportado", f"PDF exportado correctamente:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar el PDF:\n{e}")

    def _render_pdf_ene_may(self, out_path: str, year: int, header_title: str):
        """
        Layout tipo lista por mes (columnas), similar a la imagen:
        - 5 columnas: Enero..Mayo
        - Filas: días del mes (hasta 31)
        - En cada día se imprime el/los títulos de eventos (campo title)
        - Color de fondo por prioridad de tipo (Exam > Task > Class > Info)
        - SIN marca de "hoy"
        - Títulos alineados a la DERECHA
        """
        c = rl_canvas.Canvas(out_path, pagesize=landscape(letter))
        W, H = landscape(letter)

        margin = 18
        gutter = 8
        header_h = 34
        legend_h = 18

        # Header
        c.setFillColor(rl_colors.black)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(margin, H - margin - 18, header_title)
        c.setFont("Helvetica-Bold", 14)
        c.drawRightString(W - margin, H - margin - 18, f"{year} (Enero–Mayo)")

        # Legend
        lx = margin
        ly = H - margin - header_h
        c.setFont("Helvetica", 9)
        legend = [("Class", "Clase"), ("Task", "Tarea"), ("Info", "Info"), ("Exam", "Examen")]
        for typ, label in legend:
            c.setFillColor(self._pdf_type_color(typ))
            c.rect(lx, ly - 10, 14, 10, fill=1, stroke=1)
            c.setFillColor(rl_colors.black)
            c.drawString(lx + 18, ly - 9, label)
            lx += 90

        # Área disponible
        top_y = H - margin - header_h - legend_h - 6
        bot_y = margin
        usable_h = top_y - bot_y

        months = [1, 2, 3, 4, 5]
        cols = 5
        col_w = (W - 2 * margin - (cols - 1) * gutter) / cols
        x0 = margin

        rows = 31
        row_h = usable_h / (rows + 1)

        month_names = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO",
                       "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
        wd_es = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]

        month_header_fill = rl_colors.black
        month_header_text = rl_colors.white
        default_row_fill = rl_colors.HexColor("#f2f2f2")
        empty_row_fill = rl_colors.white
        grid_stroke = rl_colors.HexColor("#bdbdbd")

        font_day = ("Helvetica-Bold", 8)
        font_text = ("Helvetica", 7)

        for i, m in enumerate(months):
            col_x = x0 + i * (col_w + gutter)

            # Mes header
            y = top_y
            c.setFillColor(month_header_fill)
            c.setStrokeColor(grid_stroke)
            c.rect(col_x, y - row_h, col_w, row_h, fill=1, stroke=1)

            c.setFillColor(month_header_text)
            c.setFont("Helvetica-Bold", 10)
            c.drawCentredString(col_x + col_w / 2, y - row_h + 4, month_names[m - 1])

            last_day = calendar.monthrange(year, m)[1]

            for day in range(1, rows + 1):
                y_row_top = y - row_h * (day + 0)
                y_row = y_row_top - row_h

                if day <= last_day:
                    d_str = f"{year:04d}-{m:02d}-{day:02d}"
                    typ = self._pdf_priority_type_for_date(d_str)
                    titles = self._pdf_titles_for_date(d_str)
                    fill = self._pdf_type_color(typ) if typ else default_row_fill
                    c.setFillColor(fill)
                else:
                    c.setFillColor(empty_row_fill)

                c.setStrokeColor(grid_stroke)
                c.rect(col_x, y_row, col_w, row_h, fill=1, stroke=1)

                if day <= last_day:
                    wdi = calendar.weekday(year, m, day)  # Monday=0
                    day_label = f"{day} {wd_es[wdi]}"

                    pad = 2
                    left_w = 40
                    text_w = col_w - left_w - 2 * pad
                    text_right_x = col_x + col_w - pad  # (NUEVO) para alinear a la derecha

                    c.setFillColor(rl_colors.black)
                    c.setFont(*font_day)
                    c.drawString(col_x + pad, y_row + row_h - 10, day_label)

                    if titles:
                        text = " / ".join(titles)
                        c.setFont(*font_text)

                        lines = _wrap_lines(text, text_w, font_text[0], font_text[1])
                        if len(lines) > 2:
                            lines = lines[:2]
                            if not lines[-1].endswith("…"):
                                lines[-1] = (lines[-1][:max(0, len(lines[-1]) - 2)] + "…")

                        line_y = y_row + row_h - 10
                        for li, ln in enumerate(lines):
                            # (NUEVO) alineación derecha
                            c.drawRightString(text_right_x, line_y - (li * 8), ln)

        c.showPage()
        c.save()


if __name__ == "__main__":
    app = CalendarBuilderApp()
    app.mainloop()
