# Real-time Sports Scores in Home Assistant

This integration provides real-time scores for teams and athletes (beta) in multiple professional (NBA, NFL, NHL, MLB, MLS, and more), college (NCAA), and international (soccer, golf, tennis, racing) sports using the ESPN Scoreboard APIs, and creates a sensor with attributes for the details of the game. 

This integration can be used with the [ha-teamtracker-card](https://github.com/vasqued2/ha-teamtracker-card) to display the game information in the Home Assistant dashboard.

See the [Wiki](https://github.com/vasqued2/ha-teamtracker/wiki) for FAQs, troubleshooting advise, and custom API configurations that have been already been validated.  Please contribute to help others.

This integration is a fork of the excellent [ha-nfl](https://github.com/zacs/ha-nfl) custom component by @zacs.  Thanks for the starting place!

#### Version Compatibility
 - Releases for [ha-teamtracker](https://github.com/vasqued2/ha-teamtracker) and [ha-teamtracker-card](https://github.com/vasqued2/ha-teamtracker-card) follow the MAJOR.MINOR.PATCH convention.
 - All teamtracker and teamtracker-card releases with the same MAJOR and MINOR version numbers will be compatible, regardless of PATCH version.
 - For example, any teamtracker v0.2.x will be compatible with any teamtracker-card v0.2.y.
 - Compatibility is not guaranteed across different MAJOR or MINOR version numbers.

## Supported Sports / Leagues
- Baseball - MLB
- Basketball - NBA, WNBA, NCAAM, NCAAW, WNBA
- Football - NFL, NCAAF
- Golf - PGA (beta)
- Hockey - NHL
- MMA - UFC (beta)
- U.S. Soccer - MLS, NWSL
- International Soccer - BUND (German Bundesliga), CL (Champions League), EPL (English Premiere League), LIGA (Spanish LaLiga), LIG1 (French Ligue 1), SERA (Italian Serie A), WC (World Cup)
- Racing - F1, IRL (beta)
- Tennis - ATP, WTA (beta)
- Volleyball - NCAAVB, NCAAVBW

See Custom API Configuration section below on how to set up additional sports/leagues if you know the ESPN API.

## Sensor Data

### State
The sensor is pretty simple: the main state is `PRE`, `IN`, `POST`, `BYE` or `NOT_FOUND`, but there are attributes for pretty much all aspects of the game, when available. State definitions are as you'd expect:
- `PRE`: The game is in pre-game state. This happens when ESPN publishes the pre-game info via their API.  The lead time varies based on the league.
- `IN`: The game is in progress.
- `POST`: The game has completed. 
- `BYE`: Your given team has a bye week this week. Note that attributes available are limited in this case (only abreviation, name, logo, and last updated time will be available). 
- `NOT_FOUND`: There is no game found for your team, nor is there a bye. This can happen if an invalid league or team ID has been entered.  It can also happen at the end of the season or mid-season when ESPN hasn't published the pre-game info for the next game.  See the [Wiki for help in troubleshooting tips](https://github.com/vasqued2/ha-teamtracker/wiki/Troubleshooting:--State-=--NOT_FOUND) when you believe the sensor is incorrectly in the `NOT_FOUND` state.

### Attributes
The attributes available will change based on the sensor's state, a small number are always available (league, team abbreviation, team name, and logo), but otherwise the attributes only populate when in the current state. The table below lists which attributes are available in which states. 

Some attributes are only available for certain sports.

| Name | Value | Relevant States |
| --- | --- | --- |
| `date` | Date and time of the game | `PRE` `IN` `POST` |
| `kickoff_in` | Human-readable string for how far away the game is (eg. "in 30 minutes" or "tomorrow") |  `PRE` `IN` `POST` |
| `quarter` | The current quarter of gameplay | `IN` |
| `clock` | The clock value within the quarter (should never be higher than 15:00).  Inning (MLB only). | `IN` |
| `event_name` | The name of the event being played (eg. "The Masters") | `PRE` `IN` `POST` |
| `venue` | The name of the stadium where the game is being played (eg. "Arrowhead Stadium") | `PRE` `IN` `POST` |
| `location` | The city and state where the game is being played (eg. "Pittsburgh, PA") | `PRE` `IN` `POST` |
| `tv_network` | The TV network where you can watch the game (eg. "NBC" or "NFL"). Note that if there is a national feed, it will be listed here, otherwise the local affiliate will be listed. | `PRE` `IN` `POST` |
| `odds` | The betting odds for the game (eg. "PIT -5.0") | `PRE` |
| `overunder` | The over/under betting line for the total points scored in the game (eg. "42.5"). | `PRE` |
| `possession` | The ID of the team in possession of the ball. This will correlate to `team_id` or `opponent_id` below. Note that this value will be null in between posessions (after a score, etc). | `IN` |
| `last_play` | Sentence describing the most recent play, usually including the participants from both offense and defense, and the resulting yards. Note this can be null on posession changes or in between quarters. | `IN` |
| `down_distance_text` | String for the down and yards to go (eg. "2nd and 7"). | `IN` |
| `outs` | Number of outs (MLB only). | `IN` |
| `balls` | Number of balls (MLB only)). | `IN` |
| `strikes` | Number of strikes (MLB only). | `IN` |
| `on_first` | Baserunner on first base (MLB only). | `IN` |
| `on_second` | Baserunner on second base (MLB only). | `IN` |
| `on_third` | Baserunner on third base (MLB only). | `IN` |
| `team_total_shots` | Total shots by team (MLS only). | `IN` |
| `team_shots_on_target` | Shots on net by team (MLS only). | `IN` |
| `opponent_total_shots` | Total shots by team (MLS only). | `IN` |
| `opponent_shots_on_target` | Shots on net by team (MLS only). | `IN` |
| `team_abbr` | The abbreviation for your team (ie. `SEA` for the Seahawks). | `PRE` `IN` `POST` `BYE` |
| `team_id` | A numeric ID for your team, used to match `possession` above. | `PRE` `IN` `POST` |
| `team_name` | Your team's name (eg. "Seahawks"). Note this does not include the city name. | `PRE` `IN` `POST` `BYE` |
| `team_record` | Your team's current record (eg. "2-3"). | `PRE` `IN` `POST` |
| `team_rank` | Your team's current rank (null if unranked or does not apply). | `PRE` `IN` `POST` |
| `team_homeaway` | Your team's home/away status. Either `home` or `away`. | `PRE` `IN` `POST` |
| `team_logo` | A URL for a 500px wide PNG logo for the team. | `PRE` `IN` `POST` `BYE` |
| `team_colors` | An array with two hex colors. The first is your team's primary color, and the second is their secondary color. Unless you're the Browns, in which case they are the same. | `PRE` `IN` `POST` |
| `team_score` | Your team's score. An integer. | `IN` `POST` |
| `team_win_probability` | The real-time chance your team has to win, according to ESPN. A percentage, but presented as a float. Note that this value can become null in between posession changes. | `IN` |
| `team_timeouts` | The number of remaining timeouts your team has. | `PRE` `IN` `POST` |
| `opponent_abbr` | The abbreviation for your opponent (ie. `SEA` for the Seahawks). | `PRE` `IN` `POST` `BYE` |
| `opponent_id` | A numeric ID for your opponent, used to match `possession` above. | `PRE` `IN` `POST` |
| `opponent_name` | Your opponent's name (eg. "Seahawks"). Note this does not include the city name. | `PRE` `IN` `POST` `BYE` |
| `opponent_record` | Your opponent's current record (eg. "2-3"). | `PRE` `IN` `POST` |
| `opponent_rank` | Your opponent's current rank (null if unranked or does not apply). | `PRE` `IN` `POST` |
| `opponent_homeaway` | Your opponent's home/away status. Either `home` or `away`. | `PRE` `IN` `POST` |
| `opponent_logo` | A URL for a 500px wide PNG logo for the opponent. | `PRE` `IN` `POST` `BYE` |
| `opponent_colors` | An array with two hex colors. The first is your opponent's primary color, and the second is their secondary color. | `PRE` `IN` `POST` |
| `opponent_score` | Your opponent's score. An integer. | `IN` `POST` |
| `opponent_win_probability` | The real-time chance your opponent has to win, according to ESPN. A percentage, but presented as a float. Note that this value can become null in between posession changes. | `IN` |
| `opponent_timeouts` | The number of remaining timeouts your opponent has. | `PRE` `IN` `POST` |
| `last_update` | A timestamp for the last time data was fetched for the game. If you watch this in real-time, you should notice it updating every 10 minutes, except for during the game (and for the ~20 minutes pre-game) when it updates every 5 seconds. | `PRE` `IN` `POST` `BYE` |
| `api_message` | A message giving information to help troubleshoot when the sensor is state `NOT_FOUND` | `NOT_FOUND` |


## Installation

### Manually

Clone or download this repository and copy the "teamtracker" directory to your "custom_components" directory in your config directory

```<config directory>/custom_components/teamtracker/...```
  
### HACS

1. Open the HACS section of Home Assistant.
2. Click the "..." button in the top right corner and select "Custom Repositories."
3. In the window that opens paste this Github URL.
4. In the window that opens when you select it click om "Install This Repository in HACS"
  
## Configuration

For the League, the following values are valid:
- ATP (Assc. of Tennis Professionals)*
- BUND (German Bundesliga)
- CL (Champions League)
- EPL (English Premiere League)
- F1 (Formula 1 Racing)*
- IRL (Indy Racing League)*
- LIGA (Spanish LaLiga)
- LIG1 (French Ligue 1)
- MLB (Major League Baseball)
- MLS (Major League Soccer)
- NBA (National Basketball Assc.)
- NCAAF (NCAA Football)
- NCAAM (NCAA Men's Basketball)
- NCAAW (NCAA Women's Basketball)
- NCAAVB (NCAA Men's Volleyball)
- NCAAVBW (NCAA Women's Volleyball)
- NFL (National Football League)
- NWSL (National Women's Soccer League)
- PGA (Professional Golfers' Assc.)*
- SERA (Italian Serie A)
- UFC (Ultimate Fighting Championship)*
- WC (World Cup)
- WNBA (Women's NBA)
- WTA (Women's Tennis Assc.)*
    
For the Team, you'll need to know the team ID ESPN uses for your team.  This is the 2-, 3- or 4-letter abbreviation (eg. "SEA" for Seattle or "NE" for New England) ESPN uses when space is limited.  You can generally find them at https://espn.com/ in the top scores UI, but they can also be found in other pages with team stats as well.  

NOTE:  In rare instances, the team ID will vary based on your local language.  While rare, changing the language after a sensor is set up can cause it to stop working.

For individual sports, you should specify the althlete's name in `team_id` field.  This will cause the sensor to track the competitions matching the name of the specified athlete.  You should use as much of the name (i.e. last name, full name) as needed to uniquely identify the athlete.

#### Use of a Wild Card In Place of Athlete's Name

For individual sports, you can use the single `*` character as a Wild Card in place of the athlete's name.  This will cause the sensor to match an athlete using sport-specific logic.

The Wild Card acts in the following manner
| Sport | Behavior |
| --- | --- |
| Golf | Displays the current leader and competitor in second place |
| MMA | Displays the current active fight or the next upcoming fight if none are active |
| Racing | Displays the current leader and competitor in second place |
| Tennis | Results will be unpredictable due to multiple tournaments and matches in progress at once |

## Conference ID Numbers

By default, NCAA football and basketball will only find a game if at least one of the teams playing is ranked.  In order to find games in which both teams are unranked, you must specify a Conference ID, which is a number used by ESPN to identify college conferences and other groups of teams.  Conferences ID's are not consistent across football and basketball.

The following is a list of the college conferences and the corresponding number ESPN uses for their Conference ID.  For games involving at least one ranked team, no Conference ID is needed.

| Conference | Football Conference ID | Basketball Conference ID |
| --- | --- | --- |
| ACC | 1 | 2 |
| American | 151 | 62 |
| Big 12 | 4 | 8 |
| Big Ten | 5 | 7 |
| C-USA | 12 | 11 |
| FBS Independent | 18 |  |
| Independent |  | 43 |
| MAC | 15 | 14 |
| Mountain West | 17 | 44 |
| MVC |  | 18 |
| PAC-12 | 9 | 21 | 
| SEC | 8 | 23 |
| Sun Belt | 37 | 27 |
| America East |  | 1 |
| ASUN | 176 | 46 |
| Atlantic 10 |  | 3 |
| Big East |  | 4 |
| Big Sky | 20 | 5 |
| Big South | 40 | 6 |
| Big West |  | 9 |
| CAA | 18 | 10 |
| Horizon |  | 45 |
| Ivy | 22 | 12 |
| MAAC |  | 13 |
| MEAC | 24 | 16 |
| MVFC | 21 |
| NEC | 25 | 19 |
| OVC | 26 | 20 |
| Patriot | 27 | 22 |
| Pioneer | 28 |
| SWAC | 31 | 26 |
| Southern | 29 | 24 |
| Southland | 30 | 25 |
| Summit |  | 49 |
| WAC | 16 | 30 |
| WCC |  | 29 |

The following identifiers are also valid:
| Additional Groupings | Football Conference ID | Basketball Conference ID | Description |
| --- | --- | --- | --- |
| FBS (1-A) | 80 |  | Subset of unranked FBS games |
| FCS (1-AA) | 81 |  | Subset of FCS games |
| DIVII/III | 35 |  | Subset of D2/D3 games |
| D1 |  | 50 | Subset of unranked D1 games |

### Via the "Configuration->Integrations" section of the Home Assistant UI

Search for the integration labeled "Team Tracker" and select it.  Enter the desired League from the list above and your team's ID in the UI prompt. If NCAA football or basketball, enter the Conference ID from above if desired.  You can also enter a friendly name. If you keep the default, your sensor will be `sensor.team_tracker`, otherwise it will be `sensor.friendly_name_you_picked`. 

### Manually in your `configuration.yaml` file

To create a sensor instance add the following configuration to your sensor definitions using the team_id found above.  Enclose the values in quotes to avoid unrealized conflicts w/ predefined terms in YAML (i.e. NO being interpreted as No):

```
- platform: teamtracker
  league_id: "NFL"
  team_id: "NO"
```

After you restart Home Assistant then you should have a new sensor called `sensor.team_tracker` in your system.

You can overide the sensor default name (`sensor.team_tracker`) to one of your choosing by setting the `name` option:

```
- platform: teamtracker
  league_id: "NFL"
  team_id: "NO"
  name: "Saints"
```

Using the configuration example above the sensor will then be called "sensor.saints".

To set a Conference ID for an NCAA football or basketball team, use the following:

```
  - platform: teamtracker
    league_id: "NCAAF"
    team_id: "BGSU"
    conference_id: 15
    name: "Falcons"
```

## Custom API Configuration

It is possible to configure Team Tracker to use a custom API beyond those for the pre-configured leagues.  Please note that the APIs for many of the more obscure sports will produce an error because they do not return enough data to drive the sensor.

All ESPN APIs use a URL in the following format:
https://site.api.espn.com/apis/site/v2/sports/{SPORT_PATH}/{LEAGUE_PATH}/scoreboard
where {SPORT_PATH} is the sport and {LEAGUE_PATH} is the league that the team plays in.

For example, for the NFL, the URL is https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard

If you know the URL with the scoreboard of your team, it is possible to configure Team Tracker to use it.  the [Custom API Configuration section of the Wiki](https://github.com/vasqued2/ha-teamtracker/wiki/Custom-API-Configurations) contains more details on how to determine the {SPORT_PATH} and {LEAGUE_PATH} as well as some that have been verified to work and some that are known to not be compatible.  Please update the Wiki if you try others.

The [FAQ in the Wiki](https://github.com/vasqued2/ha-teamtracker/wiki/Frequently-Asked-Questions) also contains an explanation of the types of sports that work with the teamtracker integration and those that currently do not.

### Via the "Configuration->Integrations" section of the Home Assistant UI

When using the Home Assistant UI to set up your sensor, simply enter 'XXX' in the League field.  This will trigger a second dialogue box which will allow you to enter the values for the {SPORT} and {LEAGUE}.

### Manually in your `configuration.yaml` file

To use YAML to set up your sensor, set the league_id to 'XXX' and enter the desired values for sport_path and league_path.
```
- platform: teamtracker
  league_id: "XXX"
  team_id: "OSU"
  sport_path: "volleyball"
  league_path: "womens-college-volleyball"
  name: "Buckeyes_VB"
```