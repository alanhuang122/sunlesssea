#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#    Copyright (C) 2016 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program. See <http://www.gnu.org/licenses/gpl.html>


"""
    Tools for Sunless Sea data dumps
"""

# Ideas
# - pretty(short=True), so they can use each other
#    Ex: Location.pretty(short=True) does not print description
# - make pretty uniform across indent, \n, etc. Not there already
#    Idea: functions return with trailing '\n' if there is content
#        Callers can .strip() if they want or "".join() directly
# - format +[1 to x] so it can use {{qty}} to get non-text color
# - read text statuses on numeric quality assignments/tests
#    so "QualityX := 3" => "QualityX := 3, [3's Status Description]"
#    or even "Description" (think about SAY)
# - Improve (or even completely deprecate) format_obj using better .format()
#    specs and ideas from http://code.activestate.com/recipes/577227/
# - Quality need a custom wikipage() with {{quality status}} listings
# - Improve usage():
#    - Look for "[q:{id}]" in Advanced operators
#    - show all Event and Action Requirements, as well as all Outcomes.
#        (as a side-effect, will dramatically simplify the code)

from __future__ import unicode_literals, print_function


import sys
import os
import argparse
import logging
import json
import re
import math
import collections


log = logging.getLogger(os.path.basename(os.path.splitext(__file__)[0]))

# Changed by main() on command-line args
TEST_INTEGRITY = False




################################################################################
# General helper functions

def safeprint(text=""):
    # print() chooses encoding based on stdout type, if it's a tty (terminal)
    # or file (redirect/pipe); For ttys it auto-detects the terminals's
    # preferred encoding, but for files and pipes, sys.stdout.encoding
    # defaults to None in Python 2.7, so ascii is used (ew!).
    # In this case we encode to UTF-8.
    # See https://stackoverflow.com/questions/492483
    print(unicode(text).encode(sys.stdout.encoding or 'UTF-8'))



def format_obj(fmt, obj, *args, **kwargs):
    objdict = {_:getattr(obj, _) for _ in vars(obj) if not _.startswith('_')}
    objdict.update(dict(str=str(obj), repr=repr(obj)))
    objdict.update(kwargs)
    return unicode(fmt).format(*args, **objdict)



def indent(text, level=1, pad='\t'):
    '''Indent a text. As a side-effect it also strip trailing whitespace,
        even for level = 0
    '''
    if not level:
        return text.rstrip()
    indent = level * pad
    return "{}{}".format(indent,
                         ('\n'+indent).join(text.rstrip().split('\n')))



def iif(cond, trueval, falseval=""):
    if cond:
        return trueval
    else:
        return falseval




################################################################################
# Main() and helpers

def get_datadir():
    # Linux and FreeBSD
    if sys.platform.startswith("linux") or sys.platform.startswith("freebsd"):
        import xdg.BaseDirectory as xdg
        return os.path.join(xdg.xdg_config_home,
                            "unity3d/Failbetter Games/Sunless Sea")

    # Mac OSX
    elif sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/"
                                  "Unity.Failbetter Games.Sunless Sea")

    # Windows
    elif sys.platform == "win32":
        return os.path.expanduser("~\\AppData\\LocalLow\\"
                                  "Failbetter Games\\Sunless Sea")

    return "."  # and pray for the best...



def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__)

    group = parser.add_mutually_exclusive_group()
    group.add_argument('-q', '--quiet',
                       dest='loglevel',
                       const=logging.WARNING,
                       default=logging.INFO,
                       action="store_const",
                       help="Suppress informative messages.")

    group.add_argument('-v', '--verbose',
                       dest='loglevel',
                       const=logging.DEBUG,
                       action="store_const",
                       help="Verbose mode, output extra info.")

    parser.add_argument('-c', '--check',
                        dest='check',
                        action="store_true",
                        default=False,
                        help="Perform integrity checks, takes about 20% longer.")

    parser.add_argument('-d', '--datadir',
                        dest='datadir',
                        default=get_datadir(),
                        help="Game data directory. [Default: %(default)s]")

    parser.add_argument('-f', '--format',
                        dest='format',
                        choices=('bare', 'dump', 'pretty', 'wiki', 'wikipage'),
                        default='pretty',
                        help="Output format. 'wiki' is awesome!"
                            " Available formats: [%(choices)s]."
                            " [Default: %(default)s]")

    parser.add_argument('-m', '--method',
                        dest='method',
                        choices=('usage'),
                        #default='test',
                        metavar="METHOD",
                        help="Method (operation) to execute. Not all entities have all methods"
                            " Available methods: [%(choices)s]."
                            " [Default: %(default)s]")

    parser.add_argument('-e', '--entity',
                        dest='entity',
                        choices=('locations', 'qualities', 'events', 'shops', 'autosave'),
                        default='test',
                        metavar="ENTITY",
                        help="Entity to work on."
                            " Available entities: [%(choices)s]."
                            " [Default: %(default)s]")

    parser.add_argument(dest='filter',
                        nargs='?',
                        metavar="FILTER",
                        help="Optional name filter to narrow results")

    args = parser.parse_args(argv)
    args.debug = args.loglevel == logging.DEBUG

    return args



def main(argv=None):
    global TEST_INTEGRITY
    args = parse_args(argv or [])
    logging.basicConfig(level=args.loglevel,
                        format='%(levelname)s: %(message)s')
    log.debug(args)
    TEST_INTEGRITY = args.check

    ss = SunlessSea(args.datadir)

    log.debug(ss.locations)
    log.debug(ss.qualities)
    log.debug(ss.events)
    log.debug(ss.shops)

    if args.entity in ('locations', 'qualities', 'events', 'shops'):
        entities = getattr(ss, args.entity).find(args.filter)
        if not entities:
            log.error("No %s found for %r", args.entity, args.filter)
            return
        if args.method == 'usage':
            if not args.entity == 'qualities':
                log.error("Method 'usage' only available for qualities")
                return
            safeprint(entities.usage(args.format))
            return

        if args.format == 'wiki':
            safeprint(entities.wikitable())
        elif args.format == 'wikipage':
            safeprint(entities.wikipage())
        elif args.format == 'pretty':
            safeprint(entities.pretty())
        elif args.format == 'dump':
            safeprint(entities.dump())
        else:
            safeprint(entities.bare())
        return

    elif args.entity == "autosave":
        for _ in ss.autosave.qualities.find(args.filter):
            safeprint(_)

    elif args.entity == "demo":
        for event in ss.events.at(name="Pigmote Isle"):  # ID = 102804
            safeprint(event.pretty())
            safeprint()
        location = ss.locations.get(102004)
        safeprint(repr(location))
        safeprint(location)
        locations = ss.locations.find("pigmote")
        safeprint(locations)
        for location in ss.locations[3:6]:
            safeprint(location.pretty())
        for event in ss.events.at(name="Pigmote Isle").find("rose"):
            safeprint(repr(event))
        return




################################################################################
# Classes

class Entity(object):
    '''Base class for an Entity
        Subclasses MAY override or extend _REQUIRED_FIELDS, and MAY override
        _OPTIONAL_FIELDS _and IGNORED_FIELDS
    '''

    _ENTITY_FIELDS    = set(("Id", "Name", "Description", "Image"))
    _ENTITY_REQUIRED  = set(("Id",))

    _REQUIRED_FIELDS  = set(_ENTITY_FIELDS)
    _OPTIONAL_FIELDS  = set()  # Converted to attributes using default values
    _IGNORED_FIELDS   = set()  # No attributes created

    _re_gamenote = re.compile('\[([^\]]+)]"?$')
    _re_adv = re.compile('\[(?P<key>[a-z]):(?P<value>(?:[^][]+|\[[^][]+])+)]')


    def __init__(self, data, idx=0, ss=None):
        self._data = data
        self.idx   = idx
        self.ss    = ss
        self.id    = self._data['Id']

        self.name        = self._data.get('Name', "").strip()
        self.description = self._data.get('Description', "").strip()
        self.image       = (self._data.get('Image', None) or
                            self._data.get('ImageName', ""))  # Locations

        if TEST_INTEGRITY:
            self._test_integrity()


    def _test_integrity(self):
        fields = set(self._data)

        f = ((self._ENTITY_REQUIRED |
              self._REQUIRED_FIELDS) -
             fields)
        if f:
            log.error("%r is missing REQUIRED fields: %s",
                      self, ", ".join(sorted(f)))

        f = fields - (self._ENTITY_REQUIRED |
                      self._REQUIRED_FIELDS |
                      self._OPTIONAL_FIELDS |
                      self._IGNORED_FIELDS)
        if f:
            log.warn("%r contains UNKNOWN fields: %s",
                      self, ", ".join(sorted(f)))

        if not self.ss:
            log.error("%r has no reference to a SunlessSea instance", self)


    @property
    def etype(self):
        # Just a convenience. Provisional name (and method)
        return self.__class__.__name__


    def dump(self):
        return self._data


    def bare(self, sep='\t'):
        if self.name:
            return "{}{}{}".format(self.id, sep, self.name)
        else:
            return unicode(self.id)


    def pretty(self, short=False):
        pretty = "{:d}".format(self.id)
        if self.name:        pretty += " - {}".format(self.name)
        if self.image:       pretty += " ({})".format(self.image)
        if self.description and not short:
            # Trailing '\n' is intentional, blank line after Description
            pretty += "\n\t{}\n".format(self._desc(self.description))
        #pretty += "\n"
        return pretty


    def wiki(self):
        return self.name or unicode(self.id)


    def wikirow(self):
        return format_obj(
            "|-\n"
            "| {idx}\n"
            "| {id}\n"
            "| [[{name}]]\n"
            "| {{{{game icon|{image}}}}}\n"
            "| {description}\n",
            self, description=self._parse_adv(
                "\n".join(_.strip() for _ in
                          self.description.replace("\r","").split('\n')),
                qnamefmt="[q:[[{}]]]"))


    def wikipage(self):
        return format_obj(
            "=={name}==\n"
            "* <nowiki>{repr}</nowiki>\n"
            "* {wiki}\n",
            self, entity=self, wiki=self.wiki(), repr=repr(self))


    def _desc(self, text, cut=120, elipsis="(...)"):
        '''Quotes and limits a description, and replace control characters'''
        if len(text) > cut:
            text = text[:cut-len(elipsis)] + "(...)"
        # repr() quotes and fixes \n, \r, but must get rid of 'u' prefix
        return repr(text)[1:]


    def _parse_adv(self, text, qfmt="[{name}]", dfmt="[1 to {}]",
                   noqfmt="[Quality({})]", qnamefmt="{{{}}}"):
        '''
        Parse "Advanced" strings containing references to entities in [k:v] format

        Current references are:
        [q:ID]   - Quality by ID, return its current value ("Level")
        [q:NAME] - Quality by name, return LevelDescriptionText for its Level
        [d:NUM]  - Dice roll, 1 to NUM

        Some very basic nesting is also used, as in:
        [d:[q:ID]] - Dice roll, 1 to Quality(ID).Level

        No other nestings are found, only combinations and expressions:
        "[d:[q:108665]] - [d:5] - (100 * [q:112904])"

        Altough not used, this method also supports nesting combos such as:
        "OK [d:99+[q:102898]+2*[q:112904]+10], [q:123], [q:something], [k:foo]"

        Parameters:
            opstr: String being searched for references
            qfmt:     Formatting string for Qualities looked up by ID.
                        Use Quality attribute names such as '{name}', '{id}'.
                        '{str}' for str(Quality) and '{repr}' for its repr()
            dfmt:     Formatting string for dice rolls. '{}' for the value
            noqfmt:   Formatting string for Quality ID not found in Qualities
                        '{}' for the ID
            qnamefmt: Formatting string for Quality name. No Qualities lookup
                        is actually performed, '{}' for the name content.
        '''

        result = text
        for match in re.finditer(self._re_adv, text):
            mstr, (key, value) = match.group(), match.group('key', 'value')
            subst = None
            quality = None

            # Qualities
            if key == 'q':
                # By ID
                if value.isdigit():
                    if self.ss and self.ss.qualities:
                        quality = self.ss.qualities.get(int(value))
                    if quality:
                        subst = format_obj(qfmt, quality, quality=quality)
                    else:
                        subst = noqfmt.format(value)
                        log.warning("Could not find Quality ID %s for %r in %r",
                                    value, self, text)
                # By name
                else:
                    subst = qnamefmt.format(value)

            # Dice roll
            elif key == 'd':
                subst = dfmt.format(self._parse_adv(value, qfmt, dfmt,
                                                    noqfmt, qnamefmt))

            else:
                log.warn("Unknown %r key when parsing advanced string: %r",
                         key, text)

            if subst:
                result = result.replace(mstr, subst, 1)

        return result


    def __repr__(self):
        if self.name:
            return b"<{} {:d}: {}>".format(self.__class__.__name__,
                                           self.id,
                                           repr(self.name))
        else:
            return b"<{} {:d}>".format(self.__class__.__name__,
                                       self.id)


    def __unicode__(self):
        return self.name if self.name else unicode(repr(self))


    def __str__(self):
        return self.__unicode__().encode('utf-8')



class Quality(Entity):
    _REQUIRED_FIELDS = {'Name'}
    _OPTIONAL_FIELDS = set((
        "Description",
        "Image",

        "ChangeDescriptionText",
        "LevelDescriptionText",
        'LevelImageText',

        "AvailableAt",
        "Cap",
        "Category",
        'DifficultyScaler',
        "DifficultyTestType",
        "IsSlot",
        "Nature",
        "Persistent",
        "Tag",
        'Visible',
    ))
    _IGNORED_FIELDS  = set((
        'AllowedOn',
        'AssignToSlot',
        'CssClasses',
        'Enhancements',
        'Notes',
        "Ordering",
        'OwnerName',
        'PyramidNumberIncreaseLimit',
        'QEffectPriority',
        'QualitiesPossessedList',
        'UseEvent',
        'UsePyramidNumbers',
    ))

    _status_fields = (
        ('level_status',  'LevelDescriptionText', 'Journal Descriptions'),
        ('change_status', 'ChangeDescriptionText', 'Change Descriptions'),
        ('image_status',  'LevelImageText', 'Images'),
    )


    def __init__(self, data, idx=0, ss=None):
        super(Quality, self).__init__(data=data, idx=idx, ss=ss)
        for attr, atype, default in (
            ("AvailableAt",        str,  ""),
            ("Cap",                int,  0),
            ("Category",           int,  0),
            ("DifficultyScaler",   int,  0),
            ("DifficultyTestType", int,  0),
            ("IsSlot",             bool, False),
            ("Nature",             int,  0),
            ("Persistent",         bool, False),
            ("Tag",                str,  ""),
            ("Visible",            bool, False),
        ):
            setattr(self, attr.lower(), atype(self._data.get(attr, default)))

        for attr, key, _ in self._status_fields:
            setattr(self, attr, self._parse_status(self._data.get(key, "")))


    def _parse_status(self, value):
        if not value:
            return {}
        return {int(k):v for k,v in (row.split("|") for row in value.split("~"))}


    def pretty(self):
        pretty = super(Quality, self).pretty()

        for attr, _, caption in self._status_fields:
            statuses = getattr(self, attr)
            if statuses:
                pretty += "\n\t{}: {:d}\n".format(caption, len(statuses))
                for status in sorted(statuses.iteritems()):
                    pretty += "\t\t[{}] - {}\n".format(*status)

        return pretty


    def usage(self, formatting='pretty'):
        '''
        Shows all usages, that is: all events, actions, outcomes and shops
        this appears as either a requirement, effect or tradable item

        Highly experimental! Ugly output! Cryptic coding! Use at your own risk!
            OTOH, this is awesome!
        '''

        if not formatting == 'pretty':
            log.info("You don't want pretty, but that's what you'll get")

        qid = self.id
        results = {}
        output = []
        for e in self.ss.events:
            for r in e.requirements:
                if r.quality.id == qid:
                    results.setdefault(e,
                        dict(req=None, eff=None, act={}))['req'] = r
                    break

            for f in e.effects:
                if r.quality.id == qid:
                    results.setdefault(e,
                        dict(req=None, eff=None, act={}))['eff'] = f
                    break

            for a in e.actions:
                for r in a.requirements:
                    if r.quality.id == qid:
                        results.setdefault(e,
                            dict(req=None, eff=None, act={}))['act'].setdefault(a,
                                dict(req=None, out=[]))['req'] = r
                        break

                for o in a.outcomes:
                    for f in o.effects:
                        if f.quality.id == qid:
                            results.setdefault(e,
                                dict(req=None, eff=None, act={}))['act'].setdefault(a,
                                    dict(req=None, out=[]))['out'].append(o)
                            break

        for s in self.ss.shops:
            for i in s.items:
                if qid in (i.item.id, i.currency.id):
                    results.setdefault(s, []).append(i)

        def _print(e, i=0):
            if not e:  # No object (None) or blank line ("")
                if not i:
                    output.append("")
                return

            if e.etype == "Outcome":
                out = e.pretty(short=True)
            elif e.etype == "Event":
                out = "{} {}{}".format(
                        e.etype.upper(), e,
                        " [{}]".format(e.location)
                            if e.location else "",
                )
            elif e.etype == "Shop":
                out = "{} {}{}".format(
                        e.etype.upper(), e,
                        " [{}]".format(", ".join(unicode(_)
                                                 for _ in e.locations))
                            if e.locations else "",
                )
            else:
                out = "{} {}".format(e.etype.upper(), e)

            output.append(indent(out, i))


        for e, r in sorted(results.iteritems()):
            _print(e)

            if e.etype == "Shop":
                for i in r:
                    _print(i, 1)
                _print("")
                continue

            _print(r['req'], 1)
            _print(r['eff'], 1)
            for a in r['act']:
                _print(a, 1)
                _print(r['act'][a]['req'], 2)
                for o in r['act'][a]['out']:
                    _print(o, 2)
                _print("")
            #_print("")

        return "\n".join(output).strip()



class Location(Entity):
    _REQUIRED_FIELDS = set(('Name',))
    _OPTIONAL_FIELDS = set(('Description', 'ImageName', 'MoveMessage'))


    def __init__(self, data, idx=0, ss=None):
        super(Location, self).__init__(data=data, idx=idx, ss=ss)
        self.message = self._data.get('MoveMessage', "")
        self.setting = 0


    def pretty(self):
        pretty = super(Location, self).pretty().strip()  # No '\n' after Description
        if self.message:
            pretty += "\n\tMessage: {}".format(self._desc(self.message))
        return pretty



class ShopItem(Entity):
    _REQUIRED_FIELDS = set(("Quality", "PurchaseQuality"))
    _OPTIONAL_FIELDS = set(("Cost", "SellPrice"))
    _IGNORED_FIELDS  = set(("BuyMessage", "SellMessage"))  # only dummies


    def __init__(self, data, idx=0, ss=None, shop=None):
        super(ShopItem, self).__init__(data=data, idx=idx, ss=ss)
        self.shop     = shop
        self.item     = ss.qualities.get(self._data['Quality']['Id'])
        self.currency = ss.qualities.get(self._data['PurchaseQuality']['Id'])
        self.buy      = self._data.get('Cost', 0)
        self.sell     = self._data.get('SellPrice', 0)


    def pretty(self):
        sell = ", sell for {}".format(self.sell) if self.sell else ""
        return "{0.item}: {0.buy} x {0.currency}{sell}".format(self, sell=sell)


    def __repr__(self):
        try:
            return (b"<{0.__class__.__name__} {0.id}:"
                     " {0.item!r} ({0.buy}, {0.sell})"
                     " x {0.currency!r}>".format(self))
        except AttributeError:
            # repr() requested by base class before __init__() finishes
            return b"<{0.__class__.__name__} {0.id}>".format(self)


    def __unicode__(self):
        return self.pretty()



class Shop(Entity):
    _REQUIRED_FIELDS = Entity._REQUIRED_FIELDS | set(('Availabilities',))
    _IGNORED_FIELDS  = {'Ordering'}  # a single occurrence


    def __init__(self, data, idx=0, ss=None, locations=None):
        super(Shop, self).__init__(data=data, idx=idx, ss=ss)
        self.locations = locations
        self.items = [ShopItem(data=_d, idx=_i, ss=self.ss, shop=self)
                      for _i, _d in
                      enumerate(self._data['Availabilities'], 1)]


    def pretty(self):
        pretty = super(Shop, self).pretty()
        locations = (
            "\n\tLocation: {}".format(", ".join(unicode(_) for _ in
                                                self.locations))
        ) if self.locations else ""
        items = "\n\t\t".join(_.pretty() for _ in self.items)
        return "{}{}\n\tItems: {}\n\t\t{}".format(pretty, locations, len(self.items), items)



class QualityOperator(Entity):
    '''Base Class for Effects and Requirements
        Subclasses MUST override _OPS and _OPTIONAL_FIELDS
    '''

    # Order IS relevant, hence a tuple
    _OPS = ()

    _NOT_OP  = set(('AssociatedQuality', 'Id'))
    _HIDE_OP = set(('VisibleWhenRequirementFailed',
                    'BranchVisibleWhenRequirementFailed',
                    'Priority',
                    'ForceEquip'))

    # To satisfy Entity base class
    _REQUIRED_FIELDS = {"AssociatedQuality"}
    _OPTIONAL_FIELDS = set()
    _IGNORED_FIELDS  = _HIDE_OP

    _reverse = (r'Terror$', r'Hunger$', r'Menaces:')


    def __init__(self, data, idx=0, parent=None, ss=None):
        super(QualityOperator, self).__init__(data=data, idx=idx, ss=ss)

        self.parent   = parent
        self.quality  = None
        self.operator = {_:data[_] for _ in data
                         if _ not in self._NOT_OP}

        qid = data['AssociatedQuality']['Id']
        if self.ss and self.ss.qualities:
            self.quality = self.ss.qualities.get(qid)

        if not self.quality:
            # Create a dummy one
            self.quality = Quality(data={'Id': qid, 'Name':''},
                                   ss=self.ss)
            log.warning("Could not find Quality for %r: %d",
                        parent, qid)

        # Integrity check
        if TEST_INTEGRITY:
            ops = set(self.operator) - self._HIDE_OP
            if not ops:
                log.error("No relevant operators in %r.%r",
                         self.parent, self)


    def pretty(self):
        return self._format()


    def wiki(self):
        return self._format(
            "{{{{link icon|{name}}}}}{sep}{ops}{ifsep}{ifs}",
            "{{{{link qty|{qtyops}|{name}}}}}{ifsep}{ifs}",
            "{{{{link qty|{qtyops}|{name}||*}}}}{ifsep}{ifs}",
            lvlfmt="{:+d}",
            lvladvfmt="+{}",
            advfmt='([[{name}]])',
        )


    def _format(self,
            # Defaults are suitable for __unicode__() and pretty()
            qfmt="{name}{sep}{ops}{ifsep}{ifs}",
            qfmtqty="{name} += {qtyops}{ifsep}{ifs}",
            qfmtrev="{name} += ({qtyops}){ifsep}{ifs}",
            dfmt="[1 to {}]",
            advfmt="[{name}]",
            lvlfmt="{:d}",
            lvladvfmt="{}",
            setfmt="= {}",  # ":= {}"
            ifminfmt="≥ {}",  # "if ≥ {}"
            ifmaxfmt="≤ {}",  # "if ≤ {}"
            ifeqfmt="= {}",  # "if == {}"
            ifadjfmt="= {v1} or {v2}",  # "if == {v1} or {v2}"
            elsefmt="{op}: {}",
            opsep=" and ",
            qtyopsep=" + ",
            ifsep=", only if ",
            sep=" "):

        def add(fmt, value, adv=False, *args, **kwargs):
            posopstrs.append(fmt.format((self._parse_adv(str(value),
                                                         advfmt,
                                                         dfmt)
                                         if adv else value),
                                        *args, **kwargs))

        ops = {_:self.operator[_]
               for _ in self.operator
               if _ not in self._HIDE_OP}
        posopstrs = []
        qtyopstrs = []
        ifopstrs  = []
        useqty = False  # ('Level' in ops or 'ChangeByAdvanced' in ops)

        # Loop in _OPS to preserve order
        for op in self._OPS:
            if op not in ops:
                continue

            value = ops[op]

            if op == 'OnlyIfAtLeast':
                # Look-ahead, equal values
                val = ops.get('OnlyIfNoMoreThan', None)
                if val == value:
                    ifopstrs.append(ifeqfmt.format(value))
                    ops.pop('OnlyIfNoMoreThan')

                # Look-ahead for adjacent values
                elif val == value + 1:
                    ifopstrs.append(ifadjfmt.format(v1=value, v2=val))
                    ops.pop('OnlyIfNoMoreThan')

                else:
                    # Add the string snippet
                    ifopstrs.append(ifminfmt.format(value))

            elif op == 'OnlyIfNoMoreThan':
                ifopstrs.append(ifmaxfmt.format(value))

            elif op == 'Level':
                useqty = True
                qtyopstrs.append(lvlfmt.format(value))

            elif op == 'ChangeByAdvanced':
                useqty = True
                val = re.sub(r"^[+-]?0+([+-])", "\g<1>", value)
                if val[:1] not in "+-":
                    val = lvladvfmt.format(val)

                qtyopstrs.append(self._parse_adv(val, advfmt, dfmt))

            elif op == 'SetToExactly':         add(setfmt,    value)
            elif op == 'SetToExactlyAdvanced': add(setfmt,    value, True)

            else:
                add(elsefmt, value, adv='Advanced' in op, op=op)

        if useqty:
            if any(re.match(_, self.quality.name) for _ in self._reverse):
                qfmt = qfmtrev
            else:
                qfmt = qfmtqty

        return format_obj(qfmt,
                          self.quality,
                          sep=iif(posopstrs, sep),
                          ifsep=iif(ifopstrs, ifsep),
                          ifs=opsep.join(ifopstrs),
                          ops=opsep.join(posopstrs),
                          qtyops=qtyopsep.join(qtyopstrs),
        )


    def __unicode__(self):
        return self._format()


    def __repr__(self):
        try:
            return b"<{cls} {id}: {qid} - {qname} {ops}>".format(
                cls   = self.__class__.__name__,
                id    = self.id,
                qid   = self.quality.id,
                qname = repr(self.quality.name),
                ops   = repr(self.operator))
        except AttributeError:
            # repr() requested by base class before __init__() finishes
            return b"<{cls} {id}>".format(
                cls   = self.__class__.__name__,
                id    = self.id)



class Effect(QualityOperator):
    _OPS = (
        'Level',
        'ChangeByAdvanced',
        'SetToExactly',
        'SetToExactlyAdvanced',
        'OnlyIfAtLeast',
        'OnlyIfNoMoreThan',
    )
    _OPTIONAL_FIELDS = QualityOperator._OPTIONAL_FIELDS | set(_OPS)


    def __init__(self, data, idx=0, parent=None, ss=None):
        super(Effect, self).__init__(data=data, idx=idx, parent=parent, ss=ss)

        # Integrity check
        if TEST_INTEGRITY:
            ops = set(self.operator) - self._HIDE_OP - set(('OnlyIfAtLeast',
                                                            'OnlyIfNoMoreThan'))
            if len(ops) > 1:
                log.error("Mutually exclusive operators in %r.%r: %s",
                          self.parent, self, ops)



class Requirement(QualityOperator):
    _OPS = (
        'DifficultyLevel',
        'DifficultyAdvanced',
        'MinLevel',
        'MinAdvanced',
        'MaxLevel',
        'MaxAdvanced',
    )
    _OPTIONAL_FIELDS = QualityOperator._OPTIONAL_FIELDS | set(_OPS)


    def wiki(self):
        return self._format(
            "{{{{link icon|{quality.name}}}}}{sep}{ops}",
            "{{{{challenge|{quality.name}|{}}}}}{opsep}{ops}",
            "{{{{link icon|{quality.name}}}}} challenge"
                " ({{{{action|{}%}}}} chance to win){opsep}{ops}",
            "{{{{link icon|{quality.name}}}}} {ops}{opsep}challenge,"
                " for 100%:<br>\n:<span style=\"color: teal;\">"
                "[{}]*100/{quality.difficultyscaler}</span>",
            advfmtq='([[{quality.name}]])',
        )


    def _format(self,
            # Defaults are suitable for __unicode__()
            fmt="{quality}{sep}{ops}",
            fmtcha="{quality} challenge ({} for 100%){opsep}{ops}",
            fmtchaluck="{quality} challenge ({}%){opsep}{ops}",
            fmtchaadv="{quality} challenge: "
                        "({})*100/{quality.difficultyscaler}{opsep}{ops}",
            sep=" ",  # only if there are more operators
            opsep=" and ",  # separator between operators
            advfmtd="[1 to {}]", advfmtq="[{quality}]",  # Advanced format
            # Known operators
            minfmt="≥ {}",
            maxfmt="≤ {}",
            eqfmt ="= {}",
            adjfmt="= {v1} or {v2}",
            # Unknwn operator
            elsefmt="{op}: {}",
    ):

        def add(fmt, value=None, adv=False, *args, **kwargs):
            opstrs.append(fmt.format((self._parse_adv(str(value),
                                                         advfmtq,
                                                         advfmtd)
                                         if adv else value),
                                        *args, **kwargs))

        ops = {_:self.operator[_]
               for _ in self.operator
               if _ not in self._HIDE_OP}
        opstrs = []

        # Loop in _OPS to preserve order
        for op in self._OPS:
            if op not in ops:
                continue

            value = ops[op]

            if op == 'MinLevel':
                # Look-ahead for MaxLevel, to combine '> x and < x' into '== x'
                val = ops.get('MaxLevel', None)
                if val == value:
                    add(eqfmt, value)
                    ops.pop('MaxLevel')

                # Look-ahead for adjacent values, combine into '== x or y'
                elif val == value + 1:
                    add(adjfmt, None, v1=value, v2=val)
                    ops.pop('MaxLevel')

                else:
                    # Add the string snippet
                    add(minfmt, value)

            elif op == 'MinAdvanced':
                # Look-ahead for equal values
                val = ops.get('MaxAdvanced', None)
                if val == value:
                    add(eqfmt, value, True)
                    ops.pop('MaxAdvanced')
                else:
                    add(minfmt, value, True)

            elif op == 'DifficultyLevel':
                if self.quality.category == 2000:  # "Luck", ID=432
                    fmt   = fmtchaluck
                    value = 50 - value * self.quality.difficultyscaler
                else:
                    fmt = fmtcha
                    value = (int(math.ceil(100.0 * value /
                                          self.quality.difficultyscaler))
                            if value and self.quality.difficultyscaler
                            else value)

            elif op == 'DifficultyAdvanced':
                fmt   = fmtchaadv
                value = self._parse_adv(value, advfmtq, advfmtd)

            elif op == 'MaxLevel':         add(maxfmt, value)
            elif op == 'MaxLevelAdvanced': add(maxfmt, value, True)
            elif op == 'MaxAdvanced':      add(maxfmt, value, True)
            else:
                add(elsefmt, value, adv='Advanced' in op, op=op)

        return fmt.format(value,
                          quality=self.quality,
                          operator=self.operator,
                          sep=iif(opstrs, sep),
                          opsep=iif(opstrs, opsep),
                          ops=opsep.join(opstrs),
        )



class BaseEvent(Entity):
    '''
    Base class for Event, Action and Effect, as they have a very similar format
        Subclasses SHOULD override or extend _OPTIONAL_FIELDS
    '''

    _OPTIONAL_FIELDS = set((
        "Name",
        "Description",
        "Image",
    ))

    _qualop_types = dict(
        requirements=('QualitiesRequired', Requirement),  # Events and Actions
        effects=     ('QualitiesAffected', Effect),       # Events and Outcomes
    )


    def __init__(self, data, idx=0, parent=None, ss=None):
        super(BaseEvent, self).__init__(data=data, idx=idx, ss=ss)

        # Only Actions and Outcomes
        self.parent = parent

        # Integrity checks
        if not TEST_INTEGRITY:
            return

        if 'ParentEvent' in self._data:
            iid = self._data['ParentEvent']['Id']
            if not parent:
                log.warn("%r should have parent with ID %d", self, iid)
            elif parent.id != iid:
                log.warn("Parent ID in object and data don't match for %r: %d vs %d",
                         parent.id, iid)


    def pretty(self, location=None, short=False):
        pretty = super(BaseEvent, self).pretty(short=short)

        if location:
            pretty += "\n\tLocation: {}".format(self.location)

        if getattr(self, 'requirements', None):
            pretty += "\n\tRequirements: {:d}\n".format(len(self.requirements))
            for item in self.requirements:
                pretty += "{}\n".format(indent(item.pretty(), 2))

        return pretty


    def _pretty_qualops(self, attr, short=False):
        '''Pretty-format lists of Requirements and Effects
            - Does NOT add leading '\n'
            - DOES add trailing '\n' IF there is content
            - Does NOT indent the optional header
            - Indent list IF there is a header
        '''
        out = []
        qualops = getattr(self, attr, None)
        if qualops:
            if not short:
                out.append("{}: {:d}".format(attr.title(), len(qualops)))
            # rely on indent() to rtrip each line
            out.extend(indent(_.pretty(), 0 if short else 1) for _ in qualops)
            out.append("")  # add trailing '\n' only if here IS content
        return "\n".join(out)


    def _create_qualops(self, attr):
        key, cls = self._qualop_types[attr]
        iids = []  # needed just for the integrity check
        for i, item in enumerate(self._data[key], 1):
            if TEST_INTEGRITY:
                iid = item['AssociatedQuality']['Id']
                if iid in iids:
                    log.error('Duplicate quality %d in %s for %r',
                              iid, attr, self)
                else:
                    iids.append(iid)
            yield cls(data=item, idx=i, parent=self, ss=self.ss)



class Event(BaseEvent):
    '''"Root" events, such as Port Interactions'''

    _REQUIRED_FIELDS = set((
        "ChildBranches",
        'QualitiesRequired',
        'QualitiesAffected',
    ))
    _OPTIONAL_FIELDS = BaseEvent._OPTIONAL_FIELDS | set((
        "Autofire",
        'Category',
        'LimitedToArea',
    ))
    _IGNORED_FIELDS  = set((
        'CanGoBack',
        'ChallengeLevel',
        "Deck",
        "Distribution",
        'ExoticEffects',
        "Ordering",
        "Setting",
        "Stickiness",
        'Transient',
        "Urgency",
    ))


    def __init__(self, data, idx=0, ss=None):
        super(Event, self).__init__(data=data, idx=idx, ss=ss)

        self.autofire = self._data.get("Autofire", False)
        self.category = self._data.get("Category", 0)

        self.location = None
        if 'LimitedToArea' in self._data:
            iid = self._data['LimitedToArea']['Id']
            if self.ss and self.ss.locations:
                self.location = ss.locations.get(iid)

            if not self.location:
                log.warning("Could not find Location for %r: %d", self, iid)
                self.location = Location(self._data['LimitedToArea'])

        self.requirements = list(self._create_qualops('requirements'))
        self.effects      = list(self._create_qualops('effects'))

        self.actions = []
        for i, item in enumerate(self._data.get('ChildBranches', []), 1):
            self.actions.append(Action(data=item, idx=i, parent=self, ss=self.ss))


    def pretty(self, short=False):
        out = [super(Event, self).pretty(location=self.location,
                                         short=short).strip()]

        out.append(indent(self._pretty_qualops('effects', short=short)))

        if self.actions:
            out.append("\tActions: {:d}".format(len(self.actions)))
            out.append("\n\n".join(indent(_.pretty(), 2) for _ in self.actions))

        return "\n".join(filter(None, out)) + '\n'


    def wikipage(self):
        linked, inloc = (
            '|linked       = {{{{link icon|{.location}}}}}\n'.format(self),
            " in [[{.location}]]".format(self),
        ) if self.location else ("", "")

        header=(
            '=={self.name}==\n'
            '{{{{Infobox story\n'
            '|name         = {self.name}\n'
            '|image        = SS {self.image}gaz.png\n'
            '|id           = {self.id}\n'
            '|px           = 260px\n'
            '|category     = {self.category}\n'
#            '|type         = [[Story Event#Pigmote Isle|Pigmote Isle]]'
            '{linked}'
            '}}}}\n'
            "'''{self.name}''' is a [[Sunless Sea]] [[Story Event]]{inloc}"
        ).format(**locals())

        description=(
            '===Description===\n'
            "''\"{.description}\"''"
        ).format(self) if self.description else ""

        requirements=(
            '===Trigger Conditions===\n'
            "'''{}''' requires all the following conditions:"
            ).format(self) + "".join(
            '\n* {}'
            .format(_.wiki()) for _ in self.requirements
        ) if self.requirements else ""

        effects=(
            '===Effects===\n'
            "'''{}''' automatically causes the following effects:"
            ).format(self) + "".join(
            '\n* {}'
            .format(_.wiki()) for _ in self.requirements
        ) if self.effects else ""

        actions = (
            '===Interactions===\n'
            '{{| class="ss-table" style="width: 100%;"\n'
            '! style="width:20%;" | Interaction\n'
            '! style="width:30%;" | Unlocked by\n'
            '! style="width:30%;" | Effects\n'
            '! style="width:20%;" | Notes\n'
            '\n'
            '{}\n'
            '|-\n|}}'
            .format("\n".join(_.wikirow() for _ in self.actions))
        ) if self.actions else ""

        return "\n\n\n----\n".join(filter(None, (
            header,
            description,
            requirements,
            effects,
            actions,
        )))



class Action(BaseEvent):
    # Order is VERY important, hence tuple
    _OUTCOME_TYPES = ('DefaultEvent',
                     'RareDefaultEvent',
                     'SuccessEvent',
                     'RareSuccessEvent')

    _REQUIRED_FIELDS = set((
        "QualitiesRequired",
        'ParentEvent',
        'DefaultEvent',
    ))
    _OPTIONAL_FIELDS = (
        set(BaseEvent._OPTIONAL_FIELDS) |
        set(_OUTCOME_TYPES[1:])         |
        set(_+"Chance" for _ in _OUTCOME_TYPES)
    )
    _IGNORED_FIELDS = set((
        'ActionCost',
        'ButtonText',
        "Ordering",
    ))

    _outcome_label_replaces = (("Event", ""),
                               ("Rare", "Rare "),
                               ("Success", "Successful"))
    _outcome_label_failed   = (("Default", "Failed"),)


    def __init__(self, data, idx=0, parent=None, ss=None):
        super(Action, self).__init__(data=data, idx=idx, parent=parent, ss=ss)

        self.requirements = list(self._create_qualops('requirements'))
        self.canfail      = 'SuccessEvent' in self._data

        self.outcomes = []
        for i, item in enumerate((_ for _ in self._OUTCOME_TYPES
                                  if _ in self._data), 1):
            self.outcomes.append(Outcome(
                 data      = self._data[item],
                 idx       = i,
                 parent    = self,
                 ss        = self.ss,
                 otype     = item,
                 chance    = self._data.get(item + 'Chance', None),
                 label     = self._outcome_label(item)))


    @property
    def gamenote(self):
        match = re.search(self._re_gamenote, self.description)
        if match:
            return match.group(1)
        return ""


    def pretty(self):
        pretty = super(Action, self).pretty().strip()

        for item in self.outcomes:
            pretty += "\n\n{}".format(indent(item.pretty(), 1))

        return pretty


    def wikirow(self):
        outcomes = len(self.outcomes)
        rows = 2 * outcomes - (0 if self.canfail else 1)
        rowspan = iif(rows > 1, '| rowspan="{}"              '.format(rows))
        note = self.gamenote  # save to avoid multiple calls to property

        def innerheader(outcome):
            return ("| {{{{style inner header{rare} "
                    "| {label} event{chance}\n"
            ).format(
                label  = outcome.label.replace(" Default", ""),         # lame
                rare   = iif("Rare" in outcome.label, "|*}}", "}}  "),  # lamer
                chance = iif(outcome.chance, " ({}% chance)".format(outcome.chance)),
            )

        def innercell(outcome):
            return "|{}{}{}\n".format(
                iif(outcome.idx < outcomes, " {{style inner cell}}     |"),
                iif(outcome.name, " ", "\n"),
                outcome.wiki(),
            )

        outcome = self.outcomes[0]
        if self.canfail:
            firstrow  = innerheader(self.outcomes[0])
            secondrow = "|-\n{}".format(innercell(outcome))
        else:
            firstrow = innercell(self.outcomes[0])
            secondrow = ""

        page = (
            "|-\n"
            "{rowspan}| {name}\n"
            "{rowspan}|\n"
            "<ul>\n"
            "{reqs}<p></p>\n"
            "</ul>\n"
            "{firstrow}"  # firstrow always contains leading '|' and trailing '\n'
            "{rowspan}|{note}\n"
        ).format(
            name=self._parse_adv(self.name, qnamefmt="[q:[[{}]]]"),
            reqs="<p></p>\n".join(_.wiki() for _ in self.requirements) or "-",
            note=iif(note, " {{{{game note|{}}}}}".format(note)),
            rowspan=rowspan,
            firstrow=firstrow,
        )

        page += secondrow

        for outcome in self.outcomes[1:]:
            page += "|-\n{}|-\n{}".format(innerheader(outcome),
                                            innercell(outcome))

        return page


    def _outcome_label(self, otype):
        label = otype
        for sfrom, sto in (self._outcome_label_replaces +
                           (self._outcome_label_failed
                            if self.canfail
                            else ())):
            label = label.replace(sfrom, sto)
        return label.capitalize()



class Outcome(BaseEvent):
    _REQUIRED_FIELDS = set()
    _OPTIONAL_FIELDS = BaseEvent._OPTIONAL_FIELDS - {'Image'} | set((
        "QualitiesAffected",
        "LinkToEvent",
    ))
    _IGNORED_FIELDS  = set((
        'Category',
        'ExoticEffects',
        'MoveToArea',
        "Urgency",
        "SwitchToSetting",
        "SwitchToSettingId",
    ))


    def __init__(self, data, idx=0, parent=None, ss=None,
                 otype=None, chance=None, label=None):
        super(Outcome, self).__init__(data=data, idx=idx, parent=parent, ss=ss)

        self.type    = otype
        self.chance  = chance
        self.label   = label
        self.trigger = self._data.get('LinkToEvent', {}).get('Id', None)
        self.effects = list(self._create_qualops('effects'))


    def pretty(self, short=False):
        out = ["{} outcome{}:".format(self.label,
            iif(self.chance, " ({}% chance)".format(self.chance)))
        ]

        if not short:
            out.append(indent(super(Outcome, self).pretty(short=True)))

        out.append(indent(self._pretty_qualops('effects', short=short)))

        if self.trigger:
            out.append("\tTrigger event: {} - {}".format(self.trigger.id,
                                                         self.trigger.name))

        return "\n".join(filter(None, out)) + '\n'


    def wiki(self):
        page = iif(self.name, "{{{{effect title|{}}}}}\n".format(self.name), "")
        page += "<ul>\n"

        for effect in self.effects:
            page += "{}<p></p>\n".format(effect.wiki())

        if self.trigger and self.trigger is not self.parent.parent:
            page += "{{{{trigger event|{}}}}}<p></p>\n".format(self.trigger.name)

        elif not self.effects:
            page += "-<p></p>\n"

        page += "</ul>"

        return page


    def __unicode__(self):
        return "{} Outcome{}{}".format(
            self.label,
            iif(self.chance, " ({}% chance)".format(self.chance)),
            iif(self.name, " '{}'".format(self.name)))



class Entities(object):
    '''Base class for entity containers. Subclasses SHOULD override EntityCls!'''
    EntityCls=Entity


    def __init__(self, data=None, entities=None, path=None, ss=None,
                 *eargs, **ekwargs):
        self._entities = {}
        self._order = []
        self.path = path
        self.ss = ss

        if entities is None:
            for idx, edata in enumerate(data, 1):
                entity = self.EntityCls(data=edata, idx=idx, ss=self.ss,
                                        *eargs, **ekwargs)
                self._entities[entity.id] = entity
                self._order.append(entity)
        else:
            for entity in entities:
                self._entities[entity.id] = entity
                self._order.append(entity)


    def find(self, name):
        '''Return Entities filtered by name, case-insensitive.
            If falsy, return all entities
        '''
        if not name:
            return self
        return self.__class__(path=self.path,
                              ss=self.ss,
                              entities=(_ for _ in self
                                        if re.search(name, _.name,
                                                     re.IGNORECASE)))


    def wikitable(self):
        table = ('{| class="ss-table sortable" style="width: 100%;"\n'
            '! Index\n'
            '! ID\n'
            '! Name\n'
            '! Icon\n'
            '! Description\n'
        )
        table += "".join((_.wikirow() for _ in self))
        table += '|-\n|}'
        return table


    def wikipage(self):
        return "\n\n\n".join(_.wikipage().strip() for _ in self)


    def dump(self):
        return [_.dump() for _ in self]


    def pretty(self):
        return "\n\n".join((_.pretty().strip() for _ in self))


    def bare(self):
        return "\n".join(_.bare() for _ in self)


    def get(self, eid, default=None):
        '''Get entity by ID'''
        return self._entities.get(eid, default)


    def __getitem__(self, val):
        if isinstance(val, int):
            return self._order[val]
        else:
            return self.__class__(path=self.path,
                                  ss=self.ss,
                                  entities=self._order[val])


    def __iter__(self):
        for entity in self._order:
            yield entity


    def __len__(self):
        return len(self._entities)


    def __unicode__(self):
        return "<{}: {:d}>".format(self.__class__.__name__,
                                   len(self._entities))


    def __str__(self):
        return self.__unicode__().encode('utf-8')



class Qualities(Entities):
    EntityCls=Quality

    def usage(self, formatting='pretty'):
        if formatting == 'wikipage':
            func = 'wikipage'
        else:
            func = 'pretty'

        return "\n\n\n\n".join(
            "\n\n".join((indent(getattr(_, func)(),0), indent(_.usage())))
            for _ in self)



class Locations(Entities):
    EntityCls=Location



class Shops(Entities):
    EntityCls=Shop



class Events(Entities):
    EntityCls=Event


    def at(self, lid=0, name=""):
        '''Return Events by location ID or name'''
        return Events(ss=self.ss,
                      entities=(_ for _
                                in self
                                if (_.location and
                                    ((lid  and _.location.id == lid) or
                                     (name and re.search(name, _.location.name,
                                                         re.IGNORECASE))))))



class SaveQuality(object):
    def __init__(self, data=None, idx=0, save=None, ss=None):
        self._data = data
        self.idx   = idx
        self.ss    = ss

        # To make SaveQualities.get() work
        self.id  = self._data['AssociatedQualityId']

        self.quality = ss.qualities.get(self.id)
        if not self.quality:
            # Create a dummy one
            self.quality = Quality(data={'Id': self.id, 'Name':''},
                                   ss=self.ss)
            log.warning("Could not find Quality for %r[%d]: %d",
                        save, idx, self.id)

        # Modifier is a value added to (base) value
        # For example Engine Power and Stats enhancements
        self.modifier =  self._data['EffectiveLevelModifier']


    @property
    def name(self):
        # To make SaveQualities.find() work
        return self.quality.name


    @property
    def value(self):
        return self._data['Level']


    @value.setter
    def value(self, value):
        self._data['Level'] = int(value)


    def dump(self):
        return self._data


    def __unicode__(self):
        modstr = ""
        if self.modifier:
            modstr = " + {} = {}".format(self.modifier,
                                         self.value + self.modifier)
        return "{0.quality} = {0.value}{1}".format(self, modstr)


    def __str__(self):
        return self.__unicode__().encode('utf-8')


    def __repr__(self):
        if self.quality.name:
            return b"<{cls} {qid}: {qname!r} = {value!r}>".format(
                cls   = self.__class__.__name__,
                qid   = self.quality.id,
                qname = self.quality.name,
                value = self.value)
        else:
            return b"<{cls} {qid} = {value!r}>".format(
                cls   = self.__class__.__name__,
                qid   = self.quality.id,
                qname = self.quality.name,
                value = self.value)



class SaveQualities(Entities):
    EntityCls = SaveQuality

    def __init__(self, *args, **kwargs):
        self.save = kwargs.get('save', None)
        super(SaveQualities, self).__init__(*args, **kwargs)



class Save(object):
    def __init__(self, data=None, ss=None, path=None):
        self._data = data
        self.path  = path
        self.ss    = ss

        self.qualities = SaveQualities(
           data=self._data['QualitiesPossessedList'],
           ss=self.ss,
           save=self,
        )


    def dump(self):
        return self._data


    def save(self):
        try:
            with open(self.path, "w") as fd:
                json.dump(self._data, fd, separators=(',',':'))
        except IOError as e:
            log.error("Could not save: %s", e)



class SunlessSea(object):
    '''
        Manager class, the one that loads the JSON files
        and call each entity container's constructor
    '''


    def __init__(self, datadir=None):
        self.datadir = datadir or get_datadir()
        self.qualities = Qualities(ss=self, **self._load('qualities'))
        self.locations = Locations(ss=self, **self._load('areas'))
        self.events    = Events(   ss=self, **self._load('events'))
        self.autosave  = Save(     ss=self, **self._load('Autosave', 'saves',
                                                         '', ordered=True))

        # Not yet a first-class citizen
        self.settings = self._create_settings()

        # First class, requires self.settings, constructor still messy
        self.shops = Shops(entities=(_ for _ in self._create_shop()), ss=self)
        self.ports = None  # soon!

        # Add 'LinkToEvent' references
        for event in self.events:
            for action in event.actions:
                for outcome in action.outcomes:
                    trigger = outcome.trigger
                    if type(trigger) is not int:
                        continue

                    outcome.trigger = self.events.get(trigger)
                    if outcome.trigger:
                        continue

                    # Create a dummy one
                    outcome.trigger = Event(ss=self,
                                            data=dict(Id=trigger,
                                                      ChildBranches=[],
                                                      QualitiesRequired=[]))
                    log.error("%r.%r.%r links to a non-existant event: %d",
                              event, action, outcome, trigger)


    def _create_shop(self):
        i = 0  # lame
        exchanges = self._load('exchanges')['data']
        for exchange in exchanges:
            locations = set(_l
                            for _ in exchange['SettingIds'] if _ in self.settings
                            for _l in self.settings[_]['locations'])

            for shop in exchange['Shops']:
                i+=1
                yield Shop(data=shop, idx=i, ss=self, locations=locations)


    def _create_settings(self):
        # Deal with the tiles, settings, areas, locations and ports mess
        settings = {}
        areas={}  # Integrity check only
        tiles = self._load('Tiles', subdir='geography')['data']
        for item, aid, sid in (((_['Name'], _t['Name'], _p['Name']),
                                _p['Area']['Id'],
                                _p['Setting']['Id'])
                                for _ in tiles
                                for _t in  _['Tiles']
                                for _p in _t['PortData']):
                if TEST_INTEGRITY:
                    if not areas.get(aid, sid) == sid:
                        log.error("Area %s is not 1:1 with Settings: %s, %s",
                                  aid, areas[aid], sid)
                    areas[aid] = sid

                location = self.locations.get(aid, None)
                if location:
                    location.setting = sid
                else:
                    # Dummy
                    location = Location(data={'Id': aid}, ss=self)
                    log.error("Location not found for port (%s): %s",
                              ", ".join(item), aid)

                settings.setdefault(
                    sid, {'locations': set()})['locations'].add(location)

        # Requires check AND debug flags... can't possibly hide this better :)
        if TEST_INTEGRITY:
            for sid, setting in settings.iteritems():
                log.debug("Locations in setting %s: %s", sid,
                          ", ".join("{0.id} - {0!s}".format(_)
                                    for _ in setting['locations']))

        return settings


    def _load(self, entity, subdir='entities', suffix="_import", ordered=False):
        path = os.path.join(self.datadir,
                            subdir,
                            "{}{}.json".format(entity, suffix))
        log.debug("Opening data file for '%-9s': %s", entity, path)
        try:
            with open(path) as fd:
                # strict=False to allow tabs inside strings
                return dict(path=path, data=json.load(fd, strict=False,
                        object_pairs_hook=(collections.OrderedDict
                                           if ordered else None)))
        except IOError as e:
            log.error("Could not load data file for '%s': %s", entity, e)
            return dict(path=path, data={})




################################################################################
# Import guard

if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as e:
        log.critical(e, exc_info=True)
        sys.exit(1)
    except KeyboardInterrupt:
        pass
