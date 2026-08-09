"""Save editor for EarthBound Beginnings Remake."""

#: Single source of truth for the version. pyproject.toml reads it from here,
#: the GUI shows it in Help > About, and CI tags the release from it — so
#: bumping this one line is what cuts a new release.
__version__ = "1.1.1"
