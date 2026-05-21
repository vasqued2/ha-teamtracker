# Contributing to ha-teamtracker

Thank you for your interest in contributing!

This integration supports many sports, leagues, teams, and game states across a wide variety of data providers, APIs, and edge cases. Because of this, stability, regression safety, and maintainability are very important.

## Pull Request Guidelines

### Keep PRs Focused

Please keep pull requests limited to a single logical category of change.

Good examples:
- A specific bug fix
- A focused feature
- A config flow improvement
- Translation updates
- The addition of a new data provider

Please avoid combining:
- bug fixes
- new features
- refactors
- polling changes
- UX redesigns
- breaking changes

into a single PR.

Smaller PRs are easier to review, test, discuss, and merge safely.

---

## Regression Testing

This project relies heavily on regression tests across many data providers, sports, and game conditions.

Before submitting:
- Ensure all tests pass
- Review expected-result changes carefully
- Do not blindly update expected outputs
- When adding new data providers, please be sure to add appropriate regression tests

Changes to sensor attributes or behavior should be intentional and clearly explained.

---

## Behavioral / Architectural Changes

Please open an Issue or discussion before implementing changes that:
- alter polling behavior
- change existing attribute semantics
- remove attributes
- introduce breaking changes
- add broad customization or automation scope

These changes often affect long-term maintainability and user expectations.

---

## Maintainability Matters

Not all feature requests will be accepted.

Features are evaluated based on:
- broad usefulness and applicability across multiple sports and leagues
- ability of end-users to configure/extend functionality without requiring coding changes (support for custom APIs is an example of this, users can add new sports/leagues w/o coding changes)
- API impact
- regression risk
- alignment with project scope

The goal is to keep the integration stable, understandable, and maintainable over time.

---

## Home Assistant Best Practices

Contributions should follow Home Assistant integration patterns where practical, including:
- proper async usage
- clean unload handling
- defensive API parsing
- avoiding unnecessary state churn

---

## Questions

If you're unsure whether a change fits the project direction, feel free to open an Issue or Discussion first.

The goal of these guidelines is not to discourage contributions, but to ensure changes remain maintainable, testable, and reliable across the many sports, providers, and game states supported by the integration.

## Architecture Overview

The integration is structured around provider and parser abstractions to isolate API-specific logic from sensor parsing logic.

Key components:
- `BaseSportProvider`
- `BaseSportParser`
- `provider_factory`
- `parser_factory`

New data providers should extend the appropriate base classes rather than introducing provider-specific logic into shared coordinator or entity code.

Provider responsibilities:
- API communication
- authentication/session handling
- provider-specific request formatting
- raw response retrieval
- a provider should follow one of two patterns:
  - return the raw response and leverage a new provider-specific parser, or
  - convert the raw response into the ESPN JSON format and leverage the existing ESPN parser

Parser responsibilities:
- transforming provider responses into normalized sensor data (TeamTrackerValues)
- handling sport/game-state parsing logic
- defensive data extraction

Maintaining these boundaries is important for long-term maintainability and future provider support.

---

## Testing Expectations

This project relies heavily on regression and snapshot testing.

New providers and parsers should include:
- PRE-game test cases
- IN-game test cases
- POST-game test cases

Contributions should:
- follow existing API mocking patterns
- include representative test data
- maintain strong parser test coverage (target: >80%)

Please avoid introducing live API dependencies into tests.

---

## Snapshot Testing

This project uses `syrupy` snapshot testing to validate sensor outputs across many sports and game states.

Snapshot updates should be reviewed intentionally and discussed when they change existing sensor behavior.

Do not blindly accept snapshot updates without understanding why values changed.

Changes affecting snapshots may require:
- explanation in the PR
- updated documentation
- discussion before merge

---

## AI-Assisted Contributions

AI-assisted development is allowed.

If AI tools were used to help generate or modify code:
- please disclose that in the PR description
- contributors are expected to fully review and understand all submitted changes
- contributors should be able to explain and support all code included in the PR

AI-generated code will be reviewed using the same standards as all other contributions.
