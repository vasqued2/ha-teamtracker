## Bug Fixes, Performance, Config Flow Overhaul & New Sensor Attributes

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

#### `strings.json` — Formularfelder zeigten rohe Schlüsselnamen (z.B. "search_team" statt "Teamnamen suchen")
HA Custom Components lesen Übersetzungen aus `strings.json` im Komponentenverzeichnis.
Ohne diese Datei zeigt HA die rohen Feldschlüssel (`search_team`, `team_selection`) als Labels.
`strings.json` wurde neu angelegt (identisch mit `translations/en.json`).

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

#### Komplett-Überarbeitung des Setup-Dialogs — `config_flow.py`, alle Übersetzungsdateien

Neuer mehrstufiger Flow mit hierarchischer Sport-/Liga-Auswahl:

1. **Sportart wählen** — gruppiertes Dropdown (Australian Football / Baseball / Basketball / Football / Golf / Hockey / MMA / Racing / Soccer (U.S.) / Soccer (International) / Tennis / Volleyball / Custom API)
2. **Liga wählen** — nur Ligen der gewählten Sportart. Sportarten mit nur einer Liga (AFL, MLB, PGA, NHL, UFC) überspringen diesen Schritt automatisch.
3. **Team suchen** — optionales Suchfeld + direkter ESPN-Link für die ausgewählte Liga (immer korrekt, da Liga vor dem Rendern bekannt ist)
4. **Ergebnis** — Team aus Dropdown wählen **oder** leer lassen für manuelle ID-Eingabe

Ersetzt die frühere Flat-Liste aller 30+ Ligen in einem einzigen Dropdown.

#### Integrationseintrag trägt Liga-Prefix im Namen
Statt nur `"FC Bayern München"` wird der Eintrag jetzt als `"BUND – FC Bayern München"` angelegt.
Relevant wenn mehrere Sensoren für dasselbe Team in verschiedenen Ligen existieren (z.B. BUND + CL + WC).
`CONF_NAME` (Sensor-Attribut) bleibt unverändert — kein Breaking Change.

#### Deutsche Übersetzung — `translations/de.json` *(neue Datei)*
Vollständige Übersetzung aller Config Flow Schritte und Fehlermeldungen.

#### Alle Übersetzungsdateien aktualisiert
`es.json`, `fr.json`, `pt-BR.json`, `sk.json` — neue Steps (`league`, `search`), neue Error-Keys (`cannot_fetch_teams`, `no_teams_found`), alte Liga-Liste aus Beschreibungen entfernt.

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
| `strings.json` | Bugfix (neue Datei) |
| `translations/en.json` | UX |
| `translations/de.json` | UX (neue Datei) |
| `translations/es.json` | UX |
| `translations/fr.json` | UX |
| `translations/pt-BR.json` | UX |
| `translations/sk.json` | UX |
