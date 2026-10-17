#!/usr/bin/env python3
"""Download a Supernote handwriting-recognition language pack and lay it out the
way the device's own installer does, ready to push with adb.

    python build_pack.py en_GB                 # fetch from Supernote, verify MD5, build
    python build_pack.py en_GB --zip pack.zip  # use a zip you already downloaded

Output goes to ./supernote-<locale>/dictionary/ (change with --out).
Standard library only. Unofficial; see README.md.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import urllib.request
import zipfile

API = 'https://device.supernote.com/official/equipment/language'
# Sent by Chauvet 3.30.x. Without it the server returns older packs meant for older firmware.
LANGUAGE_VERSION = 'v4'
BASE = 'recognition-assets/'


def lookup(locale):
    body = json.dumps({'countryCode': locale, 'equipmentNo': ''}).encode()
    req = urllib.request.Request(API, data=body, method='POST', headers={
        'Content-Type': 'application/json',
        'language_version': LANGUAGE_VERSION,
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        info = json.load(r)
    if not info.get('success') or not info.get('url'):
        sys.exit(f'Supernote API returned no pack for {locale!r}: {info.get("errorMsg")}\n'
                 'Check the language code - it must look like en_GB, de_DE, fr_FR.')
    return info


def download(url, dest):
    with urllib.request.urlopen(url, timeout=60) as r, open(dest, 'wb') as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)


def md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def read_lines(data):
    # Like Java's BufferedReader.readLine(): split on \n, \r or \r\n, no trailing empty line.
    text = data.decode('utf-8')
    lines = re.split(r'\r\n|\r|\n', text)
    if lines and lines[-1] == '':
        lines.pop()
    return lines


def rewrite_conf(lines):
    # Same as DownloadLanguage.createConfig in the Settings app (firmware 3.30.45).
    out = [' SetWordListSize 10' if l.startswith(' SetWordListSize') else l for l in lines]
    out.append('\r')
    start = lines.index('Name: text') if 'Name: text' in lines else 0
    for l in lines[start:]:
        if l == 'Name: text':
            out.append('Name: text-no-candidate')
        elif l.startswith(' SetWordListSize'):
            out.append(' SetWordListSize 1')
        else:
            out.append(l)
    return out


def build(zip_path, locale, out_dir):
    dictionary = os.path.join(out_dir, 'dictionary')
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        for d in ('conf', 'conf-lite'):
            src = f'{BASE}{d}/{locale}.conf'
            if src not in names:
                sys.exit(f'{src} is not in {zip_path} - wrong locale or not a v4 pack?')
            os.makedirs(os.path.join(dictionary, d), exist_ok=True)
            # Settings writes with BufferedWriter.newLine(), which is \n on Android.
            with open(os.path.join(dictionary, d, f'{locale}.conf'), 'w', encoding='utf-8', newline='') as f:
                for line in rewrite_conf(read_lines(z.read(src))):
                    f.write(line + '\n')
        folders = set()
        for name in names:
            m = re.fullmatch(BASE + r'resources/([A-Za-z0-9_-]+)/([A-Za-z0-9_.-]+)', name)
            if not m:
                continue
            folder, filename = m.groups()
            os.makedirs(os.path.join(dictionary, 'resources', folder), exist_ok=True)
            with open(os.path.join(dictionary, 'resources', folder, filename), 'wb') as f:
                f.write(z.read(name))
            folders.add(folder)
    return dictionary, sorted(folders)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('locale', help='language code, e.g. en_GB, de_DE, fr_FR')
    ap.add_argument('--zip', help='use this already-downloaded pack instead of fetching one')
    ap.add_argument('--out', help='output folder (default: ./supernote-<locale>)')
    args = ap.parse_args()
    out_dir = args.out or f'supernote-{args.locale}'
    os.makedirs(out_dir, exist_ok=True)

    if args.zip:
        zip_path = args.zip
        print(f'Using {zip_path} (MD5 {md5(zip_path)}) - not checked against Supernote')
    else:
        info = lookup(args.locale)
        zip_path = os.path.join(out_dir, info['url'].rsplit('/', 1)[-1])
        print(f'Pack:     {info["url"]}')
        print(f'Expected: MD5 {info["md5"]}, {int(info["size"]):,} bytes')
        download(info['url'], zip_path)
        got = md5(zip_path)
        if got != info['md5']:
            sys.exit(f'MD5 mismatch: got {got}. Delete {zip_path} and try again.')
        print(f'Download OK: {zip_path}')

    dictionary, folders = build(zip_path, args.locale, out_dir)
    r = '/sdcard/.data/dictionary'
    print(f'\nBuilt {dictionary}\n\nNext, with Sideloading on and the Supernote plugged in:\n')
    print(f'  adb pull {r} dictionary-backup')
    for d in ('conf', 'conf-lite'):
        print(f'  adb push "{os.path.join(dictionary, d, args.locale + ".conf")}" {r}/{d}/{args.locale}.conf')
    for folder in folders:
        print(f'  adb push "{os.path.join(dictionary, "resources", folder)}" {r}/resources/')
    print('\nThen clear the update flag and restart the device (README step 4).')


if __name__ == '__main__':
    main()
