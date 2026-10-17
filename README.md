# Supernote offline handwriting languages

Install a handwriting recognition language on a Supernote that can't get online.

Supernote downloads handwriting recognition languages on the device over Wi-Fi. If the device has no network (no Wi-Fi, a locked-down network, or the Wi-Fi taken out on purpose), there's no official way to add one, and after a firmware update it keeps asking you to "update" the languages you already had.

This repo shows how to do it from a PC instead:

1. Get the same pack the device would download, straight from Supernote's server.
2. Lay it out exactly the way the device's own installer does (`build_pack.py`).
3. Push it with `adb` and clear the "needs update" flag.

> [!WARNING]
> Unofficial. I worked this out by reading the Settings, Launcher and Notes apps in Supernote's official firmware. Back up first, and use it at your own risk. Supernote can change any of this in a future update.

## Tested on

| Device | Firmware | Language | Result |
|---|---|---|---|
| Manta (A5 X2) | Chauvet 3.30.45 (October 2026) | English (UK), `en_GB` | Works |

The Nomad (A6 X2) runs the same firmware and should behave the same, but hasn't been tested. Other languages use the same mechanism, but only `en_GB` has been tried on a device. If you try another, please open an issue with the result.

## What you need

- A PC with Python 3.8+ (only for `build_pack.py`; the [manual steps](#manual-steps-without-the-script) don't need it)
- A USB-C cable
- Google's [Android platform-tools](https://developer.android.com/tools/releases/platform-tools) for `adb`
- **Sideloading** on, on the Supernote: Settings > Security & Privacy > Sideloading > On

Plain USB file transfer (MTP) won't work: the folder the packs live in, `/sdcard/.data/`, is hidden over MTP.

## Quick start

### 1. Build the pack

```
python build_pack.py en_GB
```

This asks Supernote's API for the current pack, downloads it, checks the MD5 against what the server says, and builds `supernote-en_GB/dictionary/`. Use your own language code (`en_US`, `de_DE`, `fr_FR`, `es_ES`, `it_IT`, `nl_NL`, `pt_PT`...).

The script then prints the exact `adb push` commands for your files.

### 2. Back up the device's dictionary folder

```
adb devices
adb pull /sdcard/.data/dictionary dictionary-backup
```

### 3. Push the files

Run the commands `build_pack.py` printed. For `en_GB` they are:

```
adb push "supernote-en_GB/dictionary/conf/en_GB.conf" /sdcard/.data/dictionary/conf/en_GB.conf
adb push "supernote-en_GB/dictionary/conf-lite/en_GB.conf" /sdcard/.data/dictionary/conf-lite/en_GB.conf
adb push "supernote-en_GB/dictionary/resources/en_GB" /sdcard/.data/dictionary/resources/
```

> [!IMPORTANT]
> In **Git Bash** on Windows, paths starting with `/sdcard/` get rewritten into Windows paths and every push fails. Use PowerShell or cmd, or run `export MSYS_NO_PATHCONV=1` first.

Check the files landed in `resources/en_GB/` and not in `resources/en_GB/en_GB/`:

```
adb shell ls -la /sdcard/.data/dictionary/resources/en_GB/
```

### 4. Clear the "needs update" flag

After a firmware update, the launcher marks every downloaded (non-built-in) language as needing an update. That's what makes Settings keep asking. A successful download sets it back to 0, so do the same:

```
adb shell
content query --uri content://com.ratta.supernote.settings.provider/lang_update
content update --uri content://com.ratta.supernote.settings.provider/lang_update --bind value:i:0 --where "name='en_GB'"
content query --uri content://com.ratta.supernote.settings.provider/lang_update
exit
```

Your language should go from `value=1` to `value=0`. Leave the built-in languages alone (`en_US`, `ja_JP`, `zh_CN`, `zh_TW`, which show `value=2`). If your language has no row at all, skip this step.

### 5. Restart and select it

Restart the Supernote. Go to Settings > Display & Input > Keyboard > Handwriting. Your language should be listed with no download or update icon. Tap its circle to select it, then create a new real-time recognition note to test. Existing notes keep the language they were created with.

You can turn Sideloading off again afterwards.

## Manual steps (without the script)

**Get the link.** The device sends a POST with a `language_version: v4` header. The header matters: without it you get older packs (MyScript 2.0.3 / 2.1.0) meant for older firmware.

PowerShell:

```powershell
Invoke-RestMethod -Method Post -Uri https://device.supernote.com/official/equipment/language -Headers @{language_version='v4'} -ContentType 'application/json' -Body '{"countryCode":"en_GB","equipmentNo":""}'
```

macOS / Linux:

```sh
curl -X POST https://device.supernote.com/official/equipment/language -H 'Content-Type: application/json' -H 'language_version: v4' -d '{"countryCode":"en_GB","equipmentNo":""}'
```

The response has a `url`, an `md5` and a `size`. For `en_GB` in October 2026:

```
https://prod-language.s3.ap-northeast-1.amazonaws.com/v4/myscript-iink-recognition-text-en_GB.zip
md5 a6c9f6abdc41af69b13cd4dde98b425e, 15,454,279 bytes
```

Download it and check the MD5 (`certutil -hashfile <file> MD5` on Windows, `md5sum` on Linux, `md5` on macOS).

**Unzip it.** Inside:

```
recognition-assets/conf/en_GB.conf
recognition-assets/conf-lite/en_GB.conf
recognition-assets/resources/en_GB/*.res     (6 files in the v4 pack)
```

**Fix the two `.conf` files.** The `.res` files go on the device as they are, but the device rewrites both `.conf` files when it installs a pack:

1. Every line starting ` SetWordListSize` becomes ` SetWordListSize 10`.
2. It adds a blank line, then appends a copy of everything from `Name: text` to the end of the file, with `Name: text` renamed `Name: text-no-candidate` and ` SetWordListSize ...` set to ` SetWordListSize 1`.

Keep the leading space on those lines. Then push the files as in [step 3](#3-push-the-files), using your fixed confs and the unzipped `resources/en_GB` folder.

## How it works

Everything here comes from the Settings (`com.ratta.settings`), Launcher and Notes apps in firmware 3.30.45.

**Where packs live:** `/sdcard/.data/dictionary/`

```
conf/<locale>.conf          full-size recognition config
conf-lite/<locale>.conf     lite config
resources/<locale>/*.res    MyScript iink resources
default/<locale>            empty file naming the selected language
version_4_4_2               engine marker written by the launcher after an upgrade
```

**Download:** `DownloadLanguage.getUrl()` posts `{"countryCode", "equipmentNo"}` with the header `language_version: v4`. It downloads the zip to `dictionary/download/` and checks the MD5.

**Install:** `processFile()` unzips the pack, then rewrites `conf` and `conf-lite` with `createConfig()` (see above) and copies `resources/` across. `build_pack.py` reproduces this byte for byte. The rewritten conf even includes the stray `\r` line the device writes between sections.

**Installed list:** Settings lists languages by scanning `dictionary/conf/*.conf`. The built-in languages (`en_US`, `ja_JP`, `zh_CN`, `zh_TW`) are copied from `/vendor/etc/myscriptdc/` and listed separately.

**"Needs update":** when `version_4_4_2` is missing on boot, the launcher deletes the old built-in packs, copies the new ones from `/vendor`, and writes a row for every installed language to `content://com.ratta.supernote.settings.provider/lang_update`. Non-built-in languages get `value=1`, which is the update prompt. A successful download sets the row to `0`; deleting the language in Settings removes the row.

**Older packs on the same server, which you don't want for 3.30.x:**

| What the request sends | What you get |
|---|---|
| `language_version: v4` | `v4/myscript-iink-recognition-text-<locale>.zip` (MyScript 4.4.0) |
| no header, empty `equipmentNo` | `dictionary-myscript-iink-recognition-text-<locale>.zip` (2.1.0, 2023) |
| no header, any `equipmentNo` | `myscript-iink-recognition-text-<locale>.zip` (2.0.3, 2022) |

The v4 pack matches the firmware: its `en_US-lk-text.lite.res` is exactly the same size as the built-in one (3,300,812 bytes), and it adds the `superimposed` resources the 4.x engine uses.

## Troubleshooting

- **No `.data` folder over USB:** expected, it's hidden over MTP. Use `adb`.
- **`adb devices` shows nothing:** check Sideloading is on. Toggling it off and on while plugged in can help.
- **Deleting the language in Settings doesn't remove it:** deleting the currently selected language didn't take in testing. Select another language first. You don't need to delete anything for this method.
- **Still asks to update after a restart:** re-run the `content query` from step 4 and check your language shows `value=0`.
- **API error:** the locale code is probably wrong. Use the `xx_YY` form.

## Undo

Push the files back from `dictionary-backup`. If you want the device to offer the download again, set the flag back with `--bind value:i:1`.

## Notes

- This repo doesn't contain any language packs. They're MyScript resources distributed by Supernote, so the script downloads them from Supernote's own server.
- Not affiliated with Supernote, Ratta or MyScript.
