# Real-time Sports Scores in Home Assistant

This integration provides real-time scores for teams and athletes in multiple professional (NBA, NFL, NHL, MLB, MLS, and more), college (NCAA), and international (soccer, golf, tennis, racing, cricket) sports using the ESPN Scoreboard APIs, and creates a sensor with detailed data for the competition. Services exist to change and interact with the sensor.

This integration can be used with the [ha-teamtracker-card](https://github.com/vasqued2/ha-teamtracker-card) to display the game information in the Home Assistant dashboard.

See the [Wiki](https://github.com/vasqued2/ha-teamtracker/wiki) for FAQs, troubleshooting advise, and custom API configurations that have been already been validated.  Please contribute to help others.

This integration is a fork of the excellent [ha-nfl](https://github.com/zacs/ha-nfl) custom component by @zacs.  Thanks for the starting place!

#### Version Compatibility
 - Releases for [ha-teamtracker](https://github.com/vasqued2/ha-teamtracker) and [ha-teamtracker-card](https://github.com/vasqued2/ha-teamtracker-card) follow the MAJOR.MINOR.PATCH convention.
 - All teamtracker and teamtracker-card releases with the same MAJOR and MINOR version numbers will be compatible, regardless of PATCH version.
 - For example, any teamtracker v0.2.x will be compatible with any teamtracker-card v0.2.y.
 - Compatibility is not guaranteed across different MAJOR or MINOR version numbers.

## Supported Teams and Leagues
TeamTracker will work for any of the hundreds of teams/leagues for which an ESPN scoreboard API exists.  

A small subset of the most popular teams/leagues have been pre-configured to simplify their setup.  This is referred to as native support.  Unfortunately, given the large number of teams/leagues for which APIs exist, it is impossible to provide native support for all of them.  

The remaining teams/leagues are still supported, however they require a couple extra steps to set up.  This is referred to as setting up a Custom API Configuration.  Custom API Configurations require more steps to set up, however once set up, they behave the same way that a natively supported sensor does.  There is no difference, for example, between a team playing in a natively supported soccer league or a non-natively supported soccer league other than the extra steps needed to initially set up the non-natively supported one.

### Natively Supported (Pre-Configured) Sports / Leagues

The following leagues are supported natively:
- Australian Football - AFL (beta)
- Baseball - MLB
- Basketball - NBA, WNBA, NCAAM, NCAAW, WNBA
- Football - NFL, NCAAF, XFL
- Golf - PGA
- Hockey - NHL
- MMA - UFC
- U.S. Soccer - MLS, NWSL
- International Soccer - BUND (German Bundesliga), CL (Champions League), CLA (Conmebol Libertadores), EPL (English Premiere League), LIGA (Spanish LaLiga), LIG1 (French Ligue 1), SERA (Italian Serie A), WC (World Cup), WWC (Women's World Cup)
- Racing - F1, IRL
- Tennis - ATP, WTA
- Volleyball - NCAAVB, NCAAVBW

### Sports / Leagues Supported via Custom API Configurations

It is possible to configure Team Tracker to use a custom API beyond those for the pre-configured leagues.  

All ESPN APIs use a URL in the following format:
https://site.api.espn.com/apis/site/v2/sports/{SPORT_PATH}/{LEAGUE_PATH}/scoreboard
where {SPORT_PATH} is the sport and {LEAGUE_PATH} is the league that the team plays in.

For example, for the NFL, the URL is https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard

Once you know the URL with the scoreboard of your team, it is possible to configure Team Tracker to use it.  the [Custom API Configuration section of the Wiki](https://github.com/vasqued2/ha-teamtracker/wiki/Custom-API-Configurations) contains more details on how to determine the {SPORT_PATH} and {LEAGUE_PATH} as well as some that have been verified to work and some that are known to not be compatible.  Please update the Wiki if you try others.

The [FAQ in the Wiki](https://github.com/vasqued2/ha-teamtracker/wiki/Frequently-Asked-Questions) also contains an explanation of the types of sports that work with the teamtracker integration and those that currently do not.

The Configuration Keys section below provides more details for configuring both types of sensors.


## Installation

### Manual Installation

Clone or download this repository and copy the "teamtracker" directory to your "custom_components" directory in your config directory

```<config directory>/custom_components/teamtracker/...```
  
### Installation via HACS

Use this button:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=vasqued2&repository=ha-teamtracker&category=integration)

OR manually perform the followng:

1. Open the HACS section of Home Assistant.
2. In Integrations, click the "+ EXPLORE & DOWNLOAD REPOSITORIES" button in the bottom right corner.
3. In the window that opens search for "Team Tracker Card".
4. Select "Team Tracker Card" from the list
5. Select the "Download" button in the buttom right corner.
6. Select "Download" from the window to download the button.
7. When given the Option, Reload.


## Configuration

### Configuration Keys

The following configuration keys are available with setting up a Team Tracker sensor.

| YAML Name | UI Label | Required | Description | Valid Values |
| --- | --- | --- | --- | --- |
| name | Friendly Name| No | Friendly name for the sensor | Any valid friendly name |
| league_id | League | Yes | League ID | See below |
| team_id | Team / Athlete | Yes | Team Team ID, Athlete Name, Regular Expression | See below |
| api_lang | None | No | Overrides default API language | [ISO language code](https://www.andiamo.co.uk/resources/iso-language-codes/) |
| conference_id | Conference Number | Only if `league_id` is a NCAA sport | Conference ID  | See below |
| sport_path | Sport Path | If `league_id` is XXX | Sport path | See below |
| league_path | League Path | No | If `league_id` is XXX | See below |


#### Specify the League

The `league_id` configuration key is used the specify the league for the sensor.  The following values are valid:
- ATP (Assc. of Tennis Professionals)
- BUND (German Bundesliga)
- CL (Champions League)
- CLA (Conmebol Libertadores)
- EPL (English Premiere League)
- F1 (Formula 1 Racing)
- IRL (Indy Racing League)
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
- PGA (Professional Golfers' Assc.)
- SERA (Italian Serie A)
- UFC (Ultimate Fighting Championship)
- XFL (XFL)
- WC (World Cup)
- WNBA (Women's NBA)
- WTA (Women's Tennis Assc.)
- XXX (Custom: Specify Sport and League Path)

Using `XXX` or selecting "Custom: Specify Sport and League Path" from the UI enables the creation of a Custom API Configuration and requires the `sport_path` and `league_path` configuration keys to be defined.

#### Specify the Team

The `team_id` key is used the specifiy the team for the sensor.  It can take the form of a Team Abbreviation, Team ID, Athlete Name, Regular Expression, or a Wildcard (`*`).

| Form | Description |
| --- | --- |
| Team Abbreviation | This is the 2-, 3- or 4-letter abbreviation (eg. "SEA" for Seattle or "NE" for New England) ESPN uses when space is limited.  You can generally find them at https://espn.com/ in the top scores UI, but they can also be found in other pages with team stats as well. |
| Team ID | ESPN assigns a unique number to identify a team.  This unique number shows up in URLs and other locations. |
| Athlete Name | For sports involving individual athletes, you should use the athlete's name as the search string.  You should use as much as is needed to uniquely identify the desired athlete. |
| RegEx | Regular expressions can be used to match team names, athlete names, and rosters in competitions like Doubles Tennis.  See below for an example. |
| Wildcard | You can use the single `*` character as a Wildcard.  This will cause the sensor to match a team or athlete using sport-specific logic outlined below. |

For doubles in tennis, rosters are used instead of team names and are in the format of `{Player 1} / {Player 2}`.  You can use a regular expression to match the roster.  As an example, if you do not know the order in which the players are listed on the roster, the regular expression `.*(?:NADAL|ALCARAZ).*/.*(?:NADAL|ALCARAZ).*` will match a doubles match with Nadal and Alcaraz regardless of which player is listed first.  The names are not case sensitive.

The Wildcard acts in the following manner
| Sport | Behavior |
| --- | --- |
| Golf | Displays the current leader and competitor in second place |
| MMA | Displays the current active fight or the next upcoming fight if none are active |
| Racing | Displays the current leader and competitor in second place |
| Tennis | Results will be unpredictable due to multiple tournaments and matches in progress at once |
| Team Sports | Most useful for playoffs.  Will continually reset to display whatever team competition is in progress in the league.  Results will be unpredictable if multiple competitions are in progress at once |

#### Override the API Language

NOTE:  Team Abbreviations and Names may vary based on your local language.  While rare, changing the language after a sensor is set up can cause it to stop working.

TeamTracker will use your local language settings when calling the ESPN APIs.  Some languages are supported more robustly than others.  For example, one language may provide play-by-play updates while another will not.  For this reason, you can override your local language.  English appears to be the most robustly supported language.

If you set up the sensor using the Home Assistant UI.  You can add the override language code via the sensor's Configure button after it has been created.

If you are setting up the sensor using YAML.  You can add it to your YAML configuration.

You should use a [standard ISO language code](https://www.andiamo.co.uk/resources/iso-language-codes/) when specifying an override.

#### Specify the Conference (for NCAA Sports only)

The `conference_id` key is used the specifiy the Conference for the sensor.  It should only be used for NCAA football and basketball.  Using it for other leagues or sports will cause a `NOT_FOUND` state.

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

#### Custom API Configurations:  How to Determine the Sport Path and League Path

Setting the `league_id` configuration key to `XXX` or selecting "Custom: Specify Sport and League Path" from the UI, invokes the Custom API Configuration mode. 
 This requires you to set the `sport_path` and `league_path` configuration keys.  This section explains how to determine the correct values for these keys.

All ESPN APIs use a URL in the following format:
https://site.api.espn.com/apis/site/v2/sports/{SPORT_PATH}/{LEAGUE_PATH}/scoreboard
where {SPORT_PATH} is the sport and {LEAGUE_PATH} is the league that the team plays in.

For example, for the NFL, the URL is https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard

The [Custom API Configuration section of the Wiki](https://github.com/vasqued2/ha-teamtracker/wiki/Custom-API-Configurations) contains more details on how to determine the {SPORT_PATH} and {LEAGUE_PATH} as well as some that have been verified to work and some that are known to not be compatible.  Please update the Wiki if you try others.

The [FAQ in the Wiki](https://github.com/vasqued2/ha-teamtracker/wiki/Frequently-Asked-Questions) also contains an explanation of the types of sports that work with the teamtracker integration and those that currently do not.

Once you have used the resources referenced above to determine the correct values to use for `sport_path` and `league_path`, you should use those values in the YAML or UI configuration.


### Configuration via the "Configuration->Integrations" section of the Home Assistant UI

1. Search for the integration labeled "Team Tracker" and select it.  
2. Enter the desired League from the League List.
3. Enter the team's ID in the UI prompt. 
4. If NCAA football or basketball, enter the Conference ID from Conference ID Numbers below if desired.  
5. You can also enter a friendly name. If you keep the default, your sensor will be `sensor.team_tracker`, otherwise it will be `sensor.friendly_name_you_picked`. 

When using the Home Assistant UI to set up a Custom API Configuration, simply enter 'XXX' in the League field.  This will trigger a second dialogue box which will allow you to enter the values for the {SPORT_PATH} and {LEAGUE_PATH}.


### Manual Configuration in your `configuration.yaml` file

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

To set up a Custom API Configuration, set the league_id to 'XXX' and enter the desired values for sport_path and league_path.
```
- platform: teamtracker
  league_id: "XXX"
  team_id: "OSU"
  sport_path: "volleyball"
  league_path: "womens-college-volleyball"
  name: "Buckeyes_VB"
```

To override the API language to Spanish, set the api_lang to 'esp'.
```
- platform: teamtracker
  league_id: "NFL"
  team_id: "NO"
  name: "Saints"
  api_language: esp
```

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
| `event_url` | An ESPN URL for the event | `PRE` `IN` `POST` |
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
| `team_url` | An ESPN URL for the team. | `PRE` `IN` `POST` `BYE` |
| `team_colors` | An array with two hex colors. The first is your team's primary color, and the second is their secondary color. Unless you're the Browns, in which case they are the same. | `PRE` `IN` `POST` |
| `team_score` | Your team's score. An integer. | `IN` `POST` |
| `team_win_probability` | The real-time chance your team has to win, according to ESPN. A percentage, but presented as a float. Note that this value can become null in between posession changes. | `IN` |
| `team_winner` | Flag indicating whether the team has won the competition or not. | `POST` |
| `team_timeouts` | The number of remaining timeouts your team has. | `PRE` `IN` `POST` |
| `opponent_abbr` | The abbreviation for your opponent (ie. `SEA` for the Seahawks). | `PRE` `IN` `POST` `BYE` |
| `opponent_id` | A numeric ID for your opponent, used to match `possession` above. | `PRE` `IN` `POST` |
| `opponent_name` | Your opponent's name (eg. "Seahawks"). Note this does not include the city name. | `PRE` `IN` `POST` `BYE` |
| `opponent_record` | Your opponent's current record (eg. "2-3"). | `PRE` `IN` `POST` |
| `opponent_rank` | Your opponent's current rank (null if unranked or does not apply). | `PRE` `IN` `POST` |
| `opponent_homeaway` | Your opponent's home/away status. Either `home` or `away`. | `PRE` `IN` `POST` |
| `opponent_logo` | A URL for a 500px wide PNG logo for the opponent. | `PRE` `IN` `POST` `BYE` |
| `opponent_url` | An ESPN URL for the opponent. | `PRE` `IN` `POST` `BYE` |
| `opponent_colors` | An array with two hex colors. The first is your opponent's primary color, and the second is their secondary color. | `PRE` `IN` `POST` |
| `opponent_score` | Your opponent's score. An integer. | `IN` `POST` |
| `opponent_win_probability` | The real-time chance your opponent has to win, according to ESPN. A percentage, but presented as a float. Note that this value can become null in between posession changes. | `IN` |
| `opponent_winner` | Flag indicating whether the opponent has won the competition or not. | `POST` |
| `opponent_timeouts` | The number of remaining timeouts your opponent has. | `PRE` `IN` `POST` |
| `last_update` | A timestamp for the last time data was fetched for the game. If you watch this in real-time, you should notice it updating every 10 minutes, except for during the game (and for the ~20 minutes pre-game) when it updates every 5 seconds. | `PRE` `IN` `POST` `BYE` |
| `api_message` | A message giving information to help troubleshoot when the sensor is state `NOT_FOUND` | `NOT_FOUND` |


## Services

TeamTracker supports the following services.

| Service | Input Parameters | Description |
| --- | --- | --- |
| call_api | sport_path, league_path, team_id, conference_id (optional) | Sets the teamtracker sensor based on the input parameters, calls the ESPN API, and populates the sensor attributes. |

Details can be viewed in the Service tab in Developer Tools.
