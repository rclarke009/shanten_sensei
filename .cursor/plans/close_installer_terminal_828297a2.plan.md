---
name: Close installer Terminal
overview: After a successful Mac install, the double-click `.command` scripts leave Terminal sitting on `Press Enter to close…` (and even after Enter, the window stays). End the installer process automatically and close that Finder-launched Terminal window.
todos:
  - id: player-installer
    content: "Install-Shanten-Sensei.command: unmount, skip success read, close Finder Terminal window by script name"
    status: in_progress
  - id: dev-installer
    content: "install-macos.command: same success auto-close / error pause split"
    status: pending
isProject: false
---

# Close Terminal after Mac install

The player installer [`shanten-sensei-overlay/scripts/Install-Shanten-Sensei.command`](../shanten-sensei-overlay/scripts/Install-Shanten-Sensei.command) finishes with `open` of the app, then **blocks on** `pause()`:

```23:25:../shanten-sensei-overlay/scripts/Install-Shanten-Sensei.command
pause() {
  read -r -p "Press Enter to close…" _
}
```

That `read` is the live process. The same wait is at the end of the from-source installer [`install-macos.command`](../shanten-sensei-overlay/scripts/install-macos.command). Terminal.app also keeps the window after the shell exits unless the user changed Shell prefs.

Work is in the **overlay repo** (this Sensei repo only documents the zip).

## Success path (Finder double-click)

1. Unmount the DMG **before** finishing (`cleanup`; clear `MOUNT_POINT` so the `EXIT` trap does not detach twice).
2. Open the app as today.
3. Skip `read` on success.
4. If the parent process is `Terminal` or `login` (Finder-launched `.command`), background AppleScript to close **this** window after a short delay, matching `basename "$0"` so other Terminal windows stay open. Then `exit 0`.

Do **not** close the window when the script is run from an existing shell (`bash ~/Downloads/Install-Shanten-Sensei.command`) — parent is `zsh`/`bash`; just return to the prompt.

## Error path

Keep `Press Enter to close…` on failures so a double-clicked window does not vanish before the error can be read.

## Also update

[`install-macos.command`](../shanten-sensei-overlay/scripts/install-macos.command): same success vs error close behavior (dev `.command` has the same linger).

No doc rewrite required. A one-line INSTALL.md note is optional (“the installer Terminal window closes when it finishes”).
