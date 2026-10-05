# Localization interoperability adapter

The adapter calls the original project's pinned v2.4.0 assembly; it does not copy or relicense that engine. No engine executable is committed here. Its own compatibility checks, game-closed checks, backups, transaction rollback and restore validation remain in control. Legacy compatibility and completion dialogs still require human interaction.

For local development, stage a separately obtained official engine with `prepare-localization.ps1 -Engine <absolute-exe-path> -Destination <new-directory>`. The script verifies the published asset digest and compiles the adapter without running it. For native read-only fixture tests, set `ATREIA_LOCALIZATION_COMPONENTS` to that directory and run the localization tests. They do not prove installation or restore compatibility with a live game.

The desktop looks for these staged files in `vendor/localization`. Missing or untrusted components disable engine operations. No automatic download, elevation, installation or capture is performed. Installation and restore require a selected Steam directory and explicit confirmation; PURPLE is deliberately not assumed compatible with the Steam engine. Transaction processes have no automatic timeout and the window cannot close while a write is in progress.

Redistribution of the original engine and all of its embedded components requires a separate license/source audit. Staging for local review is not approval to publish a combined release.
