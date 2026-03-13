## Bug Fixes, Performance, Config Flow Team Search & New Sensor Attributes

### 🐛 Bug Fixes

#### `set_baseball.py` — NoneType crash bei MLB-Sensor
`clock` konnte `None` zurückgeben; direkter Slice `clock[:3]` crashte mit `AttributeError`.
None-Guard vor dem Slice ergänzt.

#### `set_values.py` — `tv_network` war `None` statt `""`
Wenn ESPN keinen TV-Sender liefert, blieb das Attribut `None`.
Jinja2-Templates in HA-Dashboards crashen bei `None`-Vergleichen. Default auf `""` geändert.

#### `sensor.py` — HA Recorder schreibt alle 5 Sekunden während Live-Games ⚠️ Breaking Change
`last_update` (Timestamp) war in `extra_state_attributes` — ändert sich bei jedem Poll →
Recorder schreibt alle 5 s einen neuen History-Eintrag → unkontrolliertes DB-Wachstum.
`last_update` wurde aus den Attributen entfernt.

> **Breaking Change:** Templates oder Automationen die `last_update` nutzen müssen angepasst werden.

#### `sensor.py` — Falsches `score_change`-Event beim zweiten Update
`_prev_team_score` blieb `None` nach dem ersten Call, da `_score_initialized` und Prev-Update
in getrennten Code-Pfaden lagen. Beim zweiten Update: `None ≠ "3"` → fälschlich ein Event gefeuert.
Logik neu strukturiert: Prev-Update und `_score_initialized` laufen jetzt immer wenn `data` vorhanden ist.

#### `event.py` — `async_process_competition_dates` crasht bei ESPN-Datumsformat
Format `"%Y-%m-%dT%H:%Mz"` erwartet literal Kleinbuchstabe `z`,
ESPN liefert Großbuchstabe `Z` (z.B. `"2026-03-13T15:30Z"`) → `ValueError` → Sensor `unavailable`.
Auf `datetime.fromisoformat` mit `Z→+00:00`-Replace umgestellt, mit try/except abgesichert.

#### `config_flow.py` — `groups: null` verursacht `AttributeError` bei Fußball-Teams
`t.get("groups", {}).get("id", "")`: wenn ESPN `"groups": null` zurückgibt (Fußball/Soccer),
liefert `.get("groups", {})` trotzdem `None` (Key existiert, Wert ist null) → `NoneType.get()` → Crash.
Fix: `(t.get("groups") or {}).get("id", "")`.

#### `config_flow.py` — Team-Dropdown zeigte nur Abkürzungen (z.B. "MUN" statt "FC Bayern München")
`vol.In(dict)` in HA: Keys = submitted Value, Values = angezeigtes Label.
Das Dict war invertiert → Abkürzungen wurden als Label angezeigt statt der vollständigen Teamnamen.

#### `config_flow.py` — `async_step_path` (XXX Custom API): `KeyError` beim Submit
Schema zeigte nur `sport_path` und `league_path`, aber der Handler griff auf `team_id` und `name` zu.
`team_id`, `conference_id` und `name` in das Formular-Schema ergänzt.

#### `__init__.py` — Session-Leak beim Entfernen eines Sensors
`async_unload_entry` suchte `hasattr(coordinator, "async_unload")`,
die Methode heißt aber `async_shutdown` → Bedingung war immer `False` → aiohttp-Session
wurde nie geschlossen. Methodenname korrigiert.

#### `__init__.py` — Cache speicherte `None` bei API-Fehler
Nach einem API-Fehler wurde `self.data_cache[key] = None` geschrieben.
Beim nächsten Poll wurde `None` aus dem Cache gelesen statt einen frischen API-Call zu machen.
Cache wird jetzt nur noch bei erfolgreichem Response aktualisiert.

#### `__init__.py` — `async_fetch_season_stats` nutzte Abkürzung statt numerischer Team-ID
ESPN `/teams/{id}` erwartet eine numerische ID (z.B. `365`), nicht die Abkürzung (`BAY`).
Die Methode nutzte `self.team_id.upper()` (Abkürzung aus der Config) → stiller 404 → `team_season_stats`
immer leer. Numerische ID wird jetzt aus `self.data["team_id"]` gelesen (verfügbar nach erstem API-Fetch).

---

### ⚡ Performance

#### Adaptives Polling-Intervall (4 Stufen) — `const.py`, `__init__.py`

| State | Intervall |
|-------|-----------|
| `IN` / `PRE` < 20 min vor Anpfiff | 5 Sekunden |
| `PRE` > 20 min vor Anpfiff | 10 Minuten |
| `POST` (Spiel beendet) | **2 Minuten** *(neu)* |
| `NOT_FOUND` / Offseason | **30 Minuten** *(neu)* |

#### Stale-Data-Fallback bei API-Ausfall — `__init__.py`
Bei API-Fehler wird der letzte bekannte Datensatz weiterverwendet statt sofort zu `NOT_FOUND` zu wechseln.
`api_message` gibt `"Stale data (API unavailable)"` aus.
Verhindert Fehlauslösung von Automationen bei kurzen Verbindungsunterbrechungen.

---

### 🖥️ Config Flow & UX

#### Team-Suche im Setup-Dialog — `config_flow.py`, `translations/en.json`
Neuer 3-Schritt-Flow:
1. Liga auswählen + optionalen Teamnamen eingeben
2. Dropdown mit Suchergebnissen aus der ESPN Teams-API **oder** manuelle Eingabe
3. Fallback auf Custom API (XXX) unverändert

#### Liga-Dropdown mit vollständigen Namen — `config_flow.py`
Zeigt jetzt `"BUND – Bundesliga"`, `"NFL – National Football League"` etc.
statt nur der Abkürzungen. Der gespeicherte Wert bleibt die Abkürzung (kein Breaking Change).

#### Deutsche Übersetzung — `translations/de.json` *(neue Datei)*
Vollständige Übersetzung aller Config Flow Schritte und Fehlermeldungen.

---

### ✨ Neue Sensor-Attribute

#### `next_games` — Nächste bis zu 3 Spiele
Array mit den nächsten geplanten Spielen, aus der bestehenden 90-Tage-Scoreboard-API-Antwort
extrahiert — **kein extra API-Call**. Default: `[]`.

```yaml
next_games:
  - date: "2026-03-15T19:00:00Z"
    event_name: "Celtics at Lakers"
    opponent: "Los Angeles Lakers"
    opponent_abbr: "LAL"
    opponent_logo: "https://..."
    home_away: "away"
    venue: "Crypto.com Arena"
```

#### `team_season_stats` — Saison-Statistiken
Separate ESPN Teams-API mit 6h Instance-Cache. Deaktiviert für Golf, Racing, Tennis, MMA.
Default: `{}`.

```yaml
team_season_stats:
  wins: 42
  losses: 20
  win_streak: 3
  points_per_game: 112.3
```

#### HA-Event `teamtracker.score_change`
Feuert während Live-Games (`state == "IN"`) bei jeder Score-Änderung ein HA-Event.
Ermöglicht Automationen ohne Sensor-State-Polling.

```yaml
entity_id: sensor.my_team
team_name: "FC Bayern München"
team_score: "2"
opponent_score: "1"
prev_team_score: "1"
prev_opponent_score: "1"
```

---

### 📁 Geänderte Dateien

| Datei | Änderungsart |
|-------|-------------|
| `set_baseball.py` | Bugfix |
| `set_values.py` | Bugfix |
| `sensor.py` | Bugfix + Feature + **Breaking Change** |
| `event.py` | Bugfix + Feature |
| `const.py` | Performance |
| `__init__.py` | Bugfix + Performance + Feature |
| `config_flow.py` | Bugfix + UX (Komplett-Überarbeitung) |
| `clear_values.py` | Feature |
| `translations/en.json` | UX |
| `translations/de.json` | UX (neue Datei) |
