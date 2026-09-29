#!/usr/bin/env python3
# Copyright 2026 Radineer
# Derived from helium-chromium/utils/name_substitution.py (GPL-3.0, The Helium Authors).
# You can use, redistribute, and/or modify this source code under
# the terms of the GPL-3.0 license that can be found in the LICENSE file.
"""
Idaten rebrand stage: the visible word "Helium" becomes "Idaten".

Runs AFTER helium-chromium's name_substitution.py and i18n_apply.py
(devutils/shared.sh prepare_sources). At that point every UI string
(Chromium's, Helium's own, the onboarding page) says "Helium", and every
.xtb translation id is the fingerprint of that "Helium" English text.

1. .grd/.grdp: per <message>: fp_old = fingerprint; apply the explicit
   rewrite (idaten_rebrand_rules.REWRITES) if any, then the word rule
   Helium -> Idaten; fp_new = fingerprint; record fp_old -> fp_new.
   Messages in EXCLUDED_MESSAGES (and any message sharing their
   fingerprint) are left alone.
2. .xtb: every <translation> whose id is in the map gets id = fp_new
   UNCONDITIONALLY (helium's replace_xtb_translation only moves the id when
   the translated text itself matched), and its text gets the language's
   rewrite (if any) and the word rule.
3. A short allowlist of code/web files whose literals are shown on screen.

Intentional mentions of Helium inside rewrite texts ("provided by imput /
Helium", "based on Helium") are protected by a sentinel while the word rule
runs. helium-chromium/ is not modified; its utils are imported read-only.
"""

import argparse
import io
import re
import sys
import tarfile
import xml.etree.ElementTree as xml
from pathlib import Path
from tarfile import TarInfo

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent / 'helium-chromium' / 'utils'))

# pylint: disable=wrong-import-position,import-error
import idaten_rebrand_rules as rules
import name_substitution_utils as hutil  # get_parser, compute_fp, add_grit_to_path
from name_substitution import get_substitutable_files  # same walk + IGNORE_DIRS as helium

# ASCII-only boundaries: never matches helium:// (lowercase), helium.computer,
# kHeliumFoo, IDS_HELIUM_X; and still matches "Heliumの" (Python's \b treats
# CJK as word characters, so \bHelium\b would miss it).
WORD_RE = re.compile(r'(?<![A-Za-z0-9_])' + rules.OLD + r'(?![A-Za-z0-9_])')
SENTINEL = '\x00KEEP_BRAND\x00'

C_STRING_RE = re.compile(r'"(?:[^"\\\n]|\\.)*"')
JS_STRING_RE = re.compile(r'"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'|`(?:[^`\\]|\\.)*`')
HTML_TITLE_RE = re.compile(r'<title>[^<]*</title>')


def _protect(text):
    return text.replace(rules.OLD, SENTINEL)


def _compile(pairs):
    return [(re.compile(p), _protect(r)) for p, r in pairs]


def compiled_rewrites():
    out = {}
    for name, per_lang in rules.REWRITES.items():
        out[name] = {lang: _compile(pairs) for lang, pairs in per_lang.items()}
        if 'en' in out[name] and 'en-GB' not in out[name]:
            out[name]['en-GB'] = out[name]['en']
    return out


def text_nodes(elem):
    """Yields (getter, setter) for .text of elem and descendants and .tail of
    descendants, in document order. <ph>/<ex> content never affects the
    fingerprint, but is visible, so it is included."""
    yield (lambda e=elem: e.text), (lambda v, e=elem: setattr(e, 'text', v))
    for child in elem:
        yield from text_nodes(child)
        yield (lambda c=child: c.tail), (lambda v, c=child: setattr(c, 'tail', v))


def apply_to_element(elem, pairs):
    """Applies rewrite pairs (each must match somewhere), then the word rule,
    then restores protected mentions. Returns (words_replaced, unmatched)."""
    nodes = list(text_nodes(elem))
    hits = [0] * len(pairs or [])
    for get, put in nodes:
        value = get()
        if not value:
            continue
        for i, (regex, repl) in enumerate(pairs or []):
            value, n = regex.subn(repl, value)
            hits[i] += n
        put(value)
    words = 0
    for get, put in nodes:
        value = get()
        if not value:
            continue
        value, n = WORD_RE.subn(rules.NEW, value)
        words += n
        put(value.replace(SENTINEL, rules.OLD))
    unmatched = [pairs[i][0].pattern for i, h in enumerate(hits) if not h]
    return words, unmatched


def plain_text(elem):
    return ''.join(get() or '' for get, _ in text_nodes(elem))


def read(path):
    return path.read_text(encoding='utf-8').replace('&#36;', '!!dollar-sign-literal!!')




def parse(text):
    return xml.fromstring(text, hutil.get_parser())


def serialize(root):
    return xml.tostring(root, encoding='unicode', xml_declaration=True)


class Stage:  # pylint: disable=too-many-instance-attributes
    def __init__(self, tree, keep_backups):
        self.tree, self.keep_backups = tree, keep_backups
        # Nothing is written until every check passed (see flush()), so a
        # failed or repeated run leaves the tree untouched.
        self.pending = []           # (path, new text)
        self.rewrites = compiled_rewrites()
        self.fp_map = {}            # old fp -> new fp
        self.fp_rewrite = {}        # old fp -> message name with rewrite rules
        self.excluded_fps = set()
        self.backups = []
        self.errors = []
        self.n = dict(grd_files=0, grd_msgs=0, grd_words=0, rewritten_msgs=0, excluded_msgs=0,
                      xtb_files=0, xtb_ids=0, xtb_words=0, xtb_rewrite_lang=0,
                      xtb_rewrite_fallback=0)
        self.rewrite_hits = {name: 0 for name in rules.REWRITES}

    def stage_write(self, path, original, text, raw=False):
        if not raw:
            original = original.replace('!!dollar-sign-literal!!', '&#36;')
            text = text.replace('!!dollar-sign-literal!!', '&#36;')
        if self.keep_backups:
            self.backups.append((str(path.relative_to(self.tree)), original))
        self.pending.append((path, text))

    def flush(self):
        for path, text in self.pending:
            path.write_text(text, encoding='utf-8')

    # -- grd ---------------------------------------------------------------
    def grd_files(self):
        return [p for p in get_substitutable_files(self.tree, ['grd', 'grdp'])
                if rules.OLD in read(p)]

    def collect_excluded(self, files):
        for path in files:
            for msg in parse(read(path)).iter('message'):
                if msg.get('name') in rules.EXCLUDED_MESSAGES:
                    self.excluded_fps.add(hutil.compute_fp(msg))

    def substitute_grds(self):
        files = self.grd_files()
        self.collect_excluded(files)
        for path in files:
            original = read(path)
            root = parse(original)
            changed = 0
            for msg in root.iter('message'):
                name = msg.get('name')
                old_fp = hutil.compute_fp(msg)
                if old_fp in self.excluded_fps:
                    self.n['excluded_msgs'] += 1
                    continue
                pairs = self.rewrites.get(name, {}).get('en')
                if pairs is None:
                    text = plain_text(msg)
                    for phrase in rules.PHRASE_GUARD:
                        if phrase in text:
                            self.errors.append(f'unclassified "{phrase}" in {name} ({path})')
                words, unmatched = apply_to_element(msg, pairs)
                if unmatched:
                    self.errors.append(f'rewrite for {name} did not match: {unmatched}')
                new_fp = hutil.compute_fp(msg)
                if pairs is not None:
                    self.rewrite_hits[name] += 1
                    self.n['rewritten_msgs'] += 1
                    other = self.fp_rewrite.setdefault(old_fp, name)
                    if other != name and rules.REWRITES[other] is not rules.REWRITES[name] \
                            and rules.REWRITES[other] != rules.REWRITES[name]:
                        self.errors.append(f'{name} and {other} share a fingerprint but have '
                                           f'different rewrite rules')
                if words or pairs is not None:
                    changed += 1
                    self.n['grd_msgs'] += 1
                    self.n['grd_words'] += words
                if new_fp == old_fp:
                    continue
                if self.fp_map.get(old_fp, new_fp) != new_fp:
                    self.errors.append(f'fingerprint {old_fp} maps to two texts ({name})')
                self.fp_map[old_fp] = new_fp
            if changed:
                self.n['grd_files'] += 1
                self.stage_write(path, original, serialize(root))
        for name, hits in self.rewrite_hits.items():
            if not hits:
                self.errors.append(f'rewrite target {name} not found in any .grd/.grdp')
        clash = self.excluded_fps & set(self.fp_map)
        if clash:
            self.errors.append(f'excluded fingerprints were remapped: {sorted(clash)}')

    # -- xtb ---------------------------------------------------------------
    def substitute_xtbs(self):
        id_re = re.compile(r'<translation id="(\d+)"')
        for path in get_substitutable_files(self.tree, ['xtb']):
            original = read(path)
            if rules.OLD not in original and \
                    not any(m.group(1) in self.fp_map for m in id_re.finditer(original)):
                continue
            root = parse(original)
            lang = root.get('lang', '')
            changed = False
            seen = set()
            for trans in root.iter('translation'):
                tid = trans.get('id')
                if tid in self.excluded_fps:
                    seen.add(tid)
                    continue
                pairs = None
                name = self.fp_rewrite.get(tid)
                if name is not None:
                    pairs = self.rewrites[name].get(lang)
                    self.n['xtb_rewrite_lang' if pairs else 'xtb_rewrite_fallback'] += 1
                words, unmatched = apply_to_element(trans, pairs)
                if unmatched:
                    self.errors.append(f'{path.name}: rewrite for {name} did not match: {unmatched}')
                if tid in self.fp_map:
                    trans.set('id', self.fp_map[tid])
                    self.n['xtb_ids'] += 1
                    changed = True
                if words:
                    self.n['xtb_words'] += words
                    changed = True
                nid = trans.get('id')
                if nid in seen and tid in self.fp_map:
                    self.errors.append(f'{path.name}: remapped id {nid} collides')
                seen.add(nid)
            if changed:
                self.n['xtb_files'] += 1
                self.stage_write(path, original, serialize(root))

    # -- code --------------------------------------------------------------
    def substitute_code(self):
        phrases = [(re.compile(re.escape(p)), _protect(r)) for p, r in rules.CODE_PHRASES]
        pattern = {'c': C_STRING_RE, 'js': JS_STRING_RE, 'html': HTML_TITLE_RE}
        for rel, kind, minimum in rules.CODE_FILES:
            path = self.tree / rel
            if not path.exists():
                self.errors.append(f'code file missing: {rel}')
                continue
            original = path.read_text(encoding='utf-8')
            total = 0

            def repl(match):
                nonlocal total
                value = match.group(0)
                for regex, rep in phrases:
                    value, n = regex.subn(rep, value)
                    total += n
                value, n = WORD_RE.subn(rules.NEW, value)
                total += n
                return value.replace(SENTINEL, rules.OLD)

            text = pattern[kind].sub(repl, original)
            print(f'code: {rel}: {total} replaced (expected >= {minimum})')
            if total < minimum:
                self.errors.append(f'code file {rel}: {total} < {minimum}')
            if text != original:
                self.stage_write(path, original, text, raw=True)


def make_tarball(tar_path, files):
    with tarfile.open(str(tar_path), 'w:gz') as tar:
        for arcname, content in files:
            data = content.encode('utf-8')
            info = TarInfo(name=arcname)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))


def main():
    parser = argparse.ArgumentParser(description='Idaten rebrand stage (Helium -> Idaten)')
    parser.add_argument('-t', metavar='source_tree', type=Path, required=True)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--backup-path', type=Path,
                       help='tar.gz of the original files, for --unsub (dev.sh flow)')
    group.add_argument('--dry-run', action='store_true')
    parser.add_argument('--unsub', action='store_true', help='restore from --backup-path')
    args = parser.parse_args()

    if not (args.t / 'OWNERS').exists():
        raise ValueError('wrong src directory')
    if args.unsub:
        with tarfile.open(str(args.backup_path), 'r:gz') as tar:
            tar.extractall(path=args.t, filter='fully_trusted')
        args.backup_path.unlink()
        return 0
    if args.backup_path and args.backup_path.exists():
        raise FileExistsError(f'{args.backup_path} already exists')

    hutil.add_grit_to_path(args.t)
    stage = Stage(args.t, keep_backups=args.backup_path is not None)
    stage.substitute_grds()
    stage.substitute_xtbs()
    stage.substitute_code()
    if not stage.errors and not args.dry_run:
        if args.backup_path:
            make_tarball(args.backup_path, stage.backups)
        stage.flush()

    n = stage.n
    print(f"grd: {n['grd_words']} words, {n['grd_msgs']} messages changed in {n['grd_files']} files; "
          f"{n['rewritten_msgs']} messages rewritten by rule; {n['excluded_msgs']} kept "
          f"(excluded, {len(stage.excluded_fps)} fingerprints); fingerprints remapped: {len(stage.fp_map)}")
    print(f"xtb: {n['xtb_ids']} ids remapped, {n['xtb_words']} words, {n['xtb_files']} files; "
          f"rewrite translations: {n['xtb_rewrite_lang']} by language rule, "
          f"{n['xtb_rewrite_fallback']} by word rule only (no rule for that language)")
    for err in stage.errors:
        print('ERROR', err, file=sys.stderr)
    if stage.errors:
        print(f'{len(stage.errors)} error(s); no file was written', file=sys.stderr)
        return 1
    print(f'{len(stage.pending)} files ' + ('would be written (dry run)' if args.dry_run else 'written'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
