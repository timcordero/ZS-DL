#!/usr/bin/env python3

import os
import re
import sys
import json
import time
import argparse
import traceback

try:
    from urllib.parse import unquote
except ImportError:
    from urllib import unquote

import requests
from tqdm import tqdm


def read_txt(abs_path):
    with open(abs_path) as f:
        return [u.strip() for u in f.readlines()]


def create_session():
    s = requests.Session()
    s.headers.update({
        'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome"
                      "/75.0.3770.100 Safari/537.36"
    })
    if 'cfg' in locals() and cfg.proxy:
        s.proxies.update({'https': 'https://' + cfg.proxy})
    return s


def decrypt_dlc(abs_path):
    # Thank you, dcrypt owner(s).
    url = "http://dcrypt.it/decrypt/paste"
    r = create_session().post(url, data={
        'content': open(abs_path)
    }
                              )
    r.raise_for_status()
    j = json.loads(r.text)
    if not j.get('success'):
        raise RuntimeError(j)
    return j['success']['links']


def parse_prefs():
    try:
        if hasattr(sys, 'frozen'):
            os.chdir(os.path.dirname(sys.executable))
        else:
            os.chdir(os.path.dirname(__file__))
    except OSError:
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-u', '--urls',
        nargs='+', required=True,
        help='URLs separated by a space or an abs path to a txt file.'
    )
    parser.add_argument(
        '-o', '--output-path',
        default=os.getcwd(),
        help='Abs output directory.'
    )
    parser.add_argument(
        '-ov', '--overwrite',
        action='store_true',
        help='Overwrite file if already exists.'
    )
    parser.add_argument(
        '-p', '--proxy',
        help='HTTPS only. <IP>:<port>.'
    )
    args = parser.parse_args()
    if args.urls[0].endswith('.txt'):
        args.urls = read_txt(args.urls[0])
    for url in args.urls:
        if url.endswith('.dlc'):
            print("Processing DLC container: " + url)
            try:
                args.urls = args.urls + decrypt_dlc(url)
            except RuntimeError as e:
                err("Failed to decrypt DLC container: " + url)
            args.urls.remove(url)
            time.sleep(1)
    return args


def err(txt):
    print(txt)
    traceback.print_exc()


def check_url(url):
    regex = r'https://www(\d{1,3}).zippyshare.com/v/([a-zA-Z\d]{8})/file.html'
    match = re.match(regex, url)
    if match:
        return match.group(1), match.group(2)
    raise ValueError("Invalid URL: " + str(url))


def extract(url, server, zippy_id):
    regex = (
        r'var a = (\d+);\s+'
        r'document.getElementById\(\'dlbutton\'\).omg = "asdasd".substr\(0, 3\);\s+'
        r'var b = document.getElementById\(\'dlbutton\'\).omg.length;\s+'
        r'document.getElementById\(\'dlbutton\'\).href = "/d/[a-zA-Z\d]{8}/"\+\(Math.pow\(a, 3\)\+b\)\+"\/(.+)";'
    )
    for _ in range(3):
        r = create_session().get(url)
        if r.status_code != 500:
            break
        time.sleep(1)
    r.raise_for_status()
    meta = re.search(regex, r.text)
    if not meta:
        raise RuntimeError('Failed to get file URL. File down or pattern changed.')
    num_1 = int(meta.group(1))
    final_num = pow(num_1, 3) + 3
    enc_fname = meta.group(2)
    file_url = "https://www{}.zippyshare.com/d/{}/{}/{}".format(server,
                                                                zippy_id,
                                                                final_num,
                                                                enc_fname)
    fname = unquote(enc_fname)
    return file_url, fname


def get_file(ref, url):
    s = create_session()
    s.headers.update({
        'Range': "bytes=0-",
        'Referer': ref
    })
    r = s.get(url, stream=True)
    del s.headers['Range']
    del s.headers['Referer']
    r.raise_for_status()
    length = int(r.headers['Content-Length'])
    return r, length


def download(ref, url, fname, odir):
    print(fname)
    abs_path = os.path.join(odir, fname)
    if os.path.isfile(abs_path):
        if 'cfg' in locals() and cfg.overwrite:
            print("File already exists locally. Will overwrite.")
        else:
            print("File already exists locally.")
            return
    r, size = get_file(ref, url)
    with open(abs_path, 'wb') as f:
        with tqdm(total=size, unit='B',
                  unit_scale=True, unit_divisor=1024,
                  initial=0, miniters=1) as bar:
            for chunk in r.iter_content(32 * 1024):
                if chunk:
                    f.write(chunk)
                    bar.update(len(chunk))


def main(url, odir=os.getcwd()):
    server, zippy_id = check_url(url)
    file_url, fname = extract(url, server, zippy_id)
    download(url, file_url, fname, odir)
    return fname


if __name__ == '__main__':
    print("""
     _____ _____     ____  __
    |__   |   __|___|    \|  |
    |   __|__   |___|  |  |  |__
    |_____|_____|   |____/|_____|		 
    """)
    cfg = parse_prefs()
    total = len(cfg.urls)
    for num, zippy_url in enumerate(cfg.urls, 1):
        print("\nURL {} of {}:".format(num, total))
        try:
            main(zippy_url)
        except RuntimeError as e:
            err('URL failed.')
