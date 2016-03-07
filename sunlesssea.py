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
# - just the caller indents the result, using indent() - no more _level madness!
# - make pretty uniform across indent, \n, etc
# - Outcomes are a dict: only Default, Success, Rare.
#    4 keys: DefaultEvent, RareDefaultEvent, SuccessEvent, RareSuccessEvent
#    Possible combinations:
#        Def+RarDef
#        Def(Fail)+RarDef(SuperFail)+Suc
#        Def(Fail)+Suc
#        Def(Fail)+Suc+RarSuc(SuperSuc)


from __future__ import unicode_literals, print_function


import sys
import os
import argparse
import logging
import json
import re


log = logging.getLogger(os.path.basename(os.path.splitext(__file__)[0]))

# Linux and FreeBSD
if sys.platform.startswith("linux") or sys.platform.startswith("freebsd"):
    import xdg.BaseDirectory as xdg
    DATADIR=os.path.join(xdg.xdg_config_home, "unity3d/Failbetter Games/Sunless Sea")

# Mac OSX
elif sys.platform == "darwin":
    DATADIR=os.path.expanduser("~/Library/Application Support/Unity.Failbetter Games.Sunless Sea")

# Windows
elif sys.platform == "win32":
    DATADIR=os.path.expanduser("~\AppData\LocalLow\Failbetter Games\Sunless Sea")

else:
    DATADIR="."  # and pray for the best...




####################################################################################
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
    objdict.update(kwargs)
    return unicode(fmt).format(*args, **objdict)


def indent(text, level=1, pad='\t'):
    '''Indent a text. As a side-effect it also rstrips (right-trim) whitespaces'''
    if not level:
        return text
    indent = level * pad
    return "{}{}".format(indent, ('\n'+indent).join(text.rstrip().split('\n')))


####################################################################################
# Main() and helpers


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

    parser.add_argument('-d', '--datadir',
                        dest='datadir',
                        default=DATADIR,
                        help="Game data directory. [Default: %(default)s]")

    parser.add_argument('-f', '--format',
                        dest='format',
                        choices=('bare', 'pretty', 'wiki'),
                        default='pretty',
                        help="Output format. 'wiki' is awesome!"
                            " Available formats: [%(choices)s]."
                            " [Default: %(default)s]")

    parser.add_argument(dest='entity',
                        nargs="?",
                        choices=('locations', 'qualities', 'events', 'demo', 'test'),
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
    args = parse_args(argv or [])
    logging.basicConfig(level=args.loglevel,
                        format='%(levelname)s: %(message)s')
    log.debug(args)

    ss = SunlessSea(args.datadir)

    log.debug(ss.locations)
    log.debug(ss.qualities)
    log.debug(ss.events)

    if args.entity in ('locations', 'qualities', 'events'):
        entities = getattr(ss, args.entity).find(args.filter)
        if args.format == 'wiki':
            safeprint(entities.wikitable())
        elif args.format == 'pretty':
            safeprint(entities.pretty())
        else:
            safeprint(entities.show())
        return

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

    # Testing area..
    event = ss.events.get(208079)
    safeprint(event.pretty())



####################################################################################
# Classes


class Entity(object):
    '''Base class for an Entity'''

    def __init__(self, data, idx=0):
        self._data = data
        self.idx   = idx
        self.id    = self._data['Id']

        self.name        = self._data.get('Name', "")
        self.description = self._data.get('Description', "")
        self.image       = (self._data.get('Image', None) or
                            self._data.get('ImageName', ""))

    def dump(self):
        return self._data

    def pretty(self):
        pretty = "{:d}".format(self.id)
        if self.name:  pretty += " - {}".format(self.name)
        if self.image: pretty += " ({})".format(self.image)
        pretty += "\n"
        return pretty

    def wikirow(self):
        return format_obj(
            "|-\n"
            "| {idx}\n"
            "| {id}\n"
            "| [[{name}]]\n"
            "| {{{{game icon|{image}}}}}\n"
            "| <nowiki>{description}</nowiki>\n",
            self)

    def _desc(self, text, cut=80, elipsis="(...)"):
        '''Quotes and limits a description, and replace control characters'''
        if len(text) > cut:
            text = text[:cut-len(elipsis)] + "(...)"
        # repr() quotes and fixes \n, \r, but must get rid of 'u' prefix
        return repr(text)[1:]

    def __repr__(self):
        if self.name:
            return b"<{} {:d}: {}>".format(self.__class__.__name__,
                                           self.id,
                                           repr(self.name))
        else:
            return b"<{} {:d}>".format(self.__class__.__name__,
                                       self.id)

    def __str__(self):
        if self.name:
            return "{:d}\t{}".format(self.id, self.name)
        else:
            return str(self.id)


class Quality(Entity):
    _jsonattrs = {"Category",
                  "LevelDescriptionText",
                  "ChangeDescriptionText",
                  "LevelImageText",  # Pure evil
                  "Nature",
                  "Tag",
                  }

    def __init__(self, data, idx=0):
        super(Quality, self).__init__(data=data, idx=idx)
        for attr in self._jsonattrs:
            setattr(self, attr.lower(), self._data.get(attr, ""))

        for attr, key in (('level_status',  'LevelDescriptionText'),
                          ('change_status', 'ChangeDescriptionText'),
                          ('image_status',  'LevelImageText')):
            setattr(self, attr, self._parse_status(self._data.get(key, "")))

    def _parse_status(self, value):
        if not value:
            return {}
        return {int(k):v for k,v in (row.split("|") for row in value.split("~"))}

    def pretty(self, _level=0):
        pretty = super(Quality, self).pretty(_level=_level)
        indent = _level * "\t"

        for attr, caption in (('level_status',  'Journal Descriptions'),
                              ('change_status', 'Change Descriptions'),
                              ('image_status',  'Images')):
            statuses = getattr(self, attr)
            if statuses:
                pretty += "{}\t{}: {:d}\n".format(indent,
                                                  caption,
                                                  len(statuses))
                for status in sorted(statuses.iteritems()):
                    pretty += "{}\t\t[{}] - {}\n".format(indent,
                                                         *status)

        return pretty


class Location(Entity):
    def __init__(self, data, idx=0):
        super(Location, self).__init__(data=data, idx=idx)
        self.message     = self._data.get('MoveMessage', "")

    def pretty(self):
        pretty = super(Location, self).pretty()
        for attr in ('message', 'description'):
            pretty += "\t{}\n".format(self._desc(getattr(self, attr)))
        return pretty


class BaseEvent(Entity):
    '''Base class for Event, Action and Effect, as they have a very similar format
        Subclasses MUST override _INVALID_FIELDS
    '''

    _OUTCOME_TYPES = ('DefaultEvent',
                     'RareDefaultEvent',
                     'SuccessEvent',
                     'RareSuccessEvent')

    _INVALID_FIELDS = ()

    def __init__(self, data, idx=0, parent=None, qualities=None):
        super(BaseEvent, self).__init__(data=data, idx=idx)

        assert self._INVALID_FIELDS, ("BaseEvent subclass without"
                                      " _INVALID_FIELDS: {}".format(self))

        # Requirements and Effects
        for key, attr, cls in (
            ('QualitiesRequired', 'requirements', Requirement),  # Only Events and Actions
            ('QualitiesAffected', 'effects',      Effect),       # Only Events and Outcomes
        ):
            if key in self._data:
                setattr(self, attr, [])
                for item in self._data[key]:
                    getattr(self, attr).append(cls(data=item,
                                                   qualities=qualities,
                                                   parent=self))

        # Only Actions and Outcomes
        if parent:
            self.parent = parent

        # Sanity checks

        for item in self._INVALID_FIELDS:
            if item in self._data and self._data[item]:
                log.warn("Invalid field '%s' in %r", item, self)

        if 'ParentEvent' in self._data:
            iid = self._data['ParentEvent']['Id']
            if not parent:
                log.warn("%r should have parent with ID %d", self, iid)
            elif parent.id != iid:
                log.warn("Parent ID in object and data don't match for %r: %d vs %d",
                         parent.id, iid)

    def pretty(self):
        pretty = "{}\n".format(super(BaseEvent, self).pretty().strip())

        if self.description:
            pretty += "\t{}\n".format(self._desc(self.description))

        if getattr(self, 'requirements', None):
            pretty += "\tRequirements: {:d}\n".format(len(self.requirements))
            for item in self.requirements:
                pretty += "{}\n".format(indent(item.pretty(), 2))

        if getattr(self, 'effects', None):
            pretty += "\tEffects: {:d}\n".format(len(self.effects))
            for item in self.effects:
                pretty += "{}\n".format(indent(item.pretty(), 2))

        return pretty


class Event(BaseEvent):
    '''"Root" events, such as Port Interactions'''

    _INVALID_FIELDS = ('ParentEvent',
                       'LinkToEvent')

    def __init__(self, data, idx=0, qualities=None, locations=None):
        super(Event, self).__init__(data=data, idx=idx, qualities=qualities)

        self.location = None
        if 'LimitedToArea' in self._data:
            iid = self._data['LimitedToArea']['Id']
            if locations:
                self.location = locations.get(iid)

            if not self.location:
                log.warning("Could not find Location for %r: %d", self, iid)
                self.location = Location(self._data['LimitedToArea'])

        self.actions = []
        for i, item in enumerate(self._data.get('ChildBranches', [])):
            self.actions.append(Action(data=item, idx=i,
                                       qualities=qualities,
                                       parent=self))

    def pretty(self):
        pretty = super(Event, self).pretty()

        if self.location:
            pretty += "\tLocation: {}\n".format(self.location)

        if self.actions:
            pretty += "\n\tActions: {:d}".format(len(self.actions))
            for item in self.actions:
                pretty += "\n{}\n".format(indent(item.pretty(), 2))

        return pretty


class Action(BaseEvent):
    _INVALID_FIELDS = ('LimitedToArea',
                       'ChildBranches',
                       'LinkToEvent',
                       'QualitiesAffected')

    def __init__(self, data, idx=0, qualities=None, parent=None):
        super(Action, self).__init__(data=data, idx=idx, qualities=qualities, parent=parent)

        self.outcomes = []
        for item in self._OUTCOME_TYPES:
            if item in self._data:
                i = self._data.get(item + 'Chance', None)
                self.outcomes.append(Outcome(data=self._data[item],
                                             qualities=qualities,
                                             parent=self,
                                             otype=item,
                                             chance=i))

    def pretty(self):
        pretty = super(Action, self).pretty()

        for item in self.outcomes:
            pretty += "\n\t{}{}:\n".format(item.type,
                                         " {}%".format(item.chance)
                                            if item.chance
                                            else "")
            pretty += indent(item.pretty(), 2)

        return pretty


class Outcome(BaseEvent):
    _INVALID_FIELDS = ('LimitedToArea',
                       'ChildBranches',
                       'QualitiesRequired')

    def __init__(self, data, idx=0, qualities=None, parent=None, otype=None, chance=None):
        super(Outcome, self).__init__(data=data, idx=idx, qualities=qualities, parent=parent)

        self.type    = otype
        self.chance  = chance
        self.trigger = self._data.get('LinkToEvent', {}).get('Id', None)

    def pretty(self):
        pretty = super(Outcome, self).pretty()

        if self.trigger:
            pretty += "\tTrigger event: {}\n".format(self.trigger)

        return pretty


class Entities(object):
    '''Base class for entity containers. Subclasses SHOULD override EntityCls!'''
    EntityCls=Entity

    def __init__(self, data=None, entities=None, *eargs, **ekwargs):
        self._entities = {}
        self._order = []

        if entities is None:
            for idx, edata in enumerate(data, 1):
                entity = self.EntityCls(data=edata, idx=idx, *eargs, **ekwargs)
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
        return self.__class__(entities=(_ for _ in self
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

    def pretty(self):
        return "\n".join((_.pretty() for _ in self))

    def show(self):
        return "\n".join((str(_) for _ in self))

    def get(self, eid, default=None):
        '''Get entity by ID'''
        return self._entities.get(eid, default)

    def __getitem__(self, val):
        entities = self._order[val]
        if len(entities) == 1:
            return entities[0]
        else:
            return self.__class__(entities=entities)

    def __iter__(self):
        for entity in self._order:
            yield entity

    def __len__(self):
        return len(self._entities)

    def __str__(self):
        return "<{}: {:d}>".format(self.__class__.__name__,
                                   len(self._entities))


class Qualities(Entities):
    EntityCls=Quality


class Locations(Entities):
    EntityCls=Location


class Events(Entities):
    EntityCls=Event

    def at(self, lid=0, name=""):
        '''Return Events by location ID or name'''
        return Events(entities=(_ for _
                                in self
                                if (_.location and
                                    ((lid  and _.location.id == lid) or
                                     (name and re.search(name, _.location.name,
                                                         re.IGNORECASE))))))


class QualityOperator(object):
    '''Base Class for Effects and Requirements'''

    _NOT_OP  = ('AssociatedQuality', 'Id')
    _HIDE_OP = ('VisibleWhenRequirementFailed', 'BranchVisibleWhenRequirementFailed')

    def __init__(self, data, qualities=None, parent=None):
        self.id       = data['Id']
        self.parent   = parent
        self.quality  = None
        self.operator = {_:data[_] for _ in data
                         if _ not in self._NOT_OP}

        qid = data['AssociatedQuality']['Id']
        if qualities:
            self.quality = qualities.get(qid)

        if not self.quality:
            # Create a dummy one
            self.quality = Quality(data['AssociatedQuality'])
            log.warning("Could not find Quality for %r: %d",
                        parent, qid)

    def _format_ops(self, ops):
        '''dict {'MaxLevel': 2, 'MinLevel': 1} => string "MaxLevel: 2, MinLevel: 1"'''
        return ", ".join(": ".join((k, str(v)))
                         for k,v in ops.iteritems()
                         if k not in self._HIDE_OP)

    def __str__(self):
        return "{quality} ({operator})".format(
            quality=self.quality,
            operator=self._format_ops(self.operator))

    def __repr__(self):
        return "<{cls} {id}: {qid} - {qname} [{ops}]>".format(
            cls   = self.__class__.__name__,
            id    = self.id,
            qid   = self.quality.id,
            qname = self.quality.name,
            ops   = self._format_ops(self.operator))

    def pretty(self, _level=0):
        return indent("{} [{}]".format(self.quality,
                                        self._format_ops(self.operator)),
                      _level)


class Effect(QualityOperator):
    pass


class Requirement(QualityOperator):
    pass


class SunlessSea(object):
    '''
        Manager class, the one that loads the JSON files
        and call each entity container's constructor
    '''
    def __init__(self, datadir=None):
        self.qualities = Qualities(data=self._load('qualities', datadir))
        self.locations = Locations(data=self._load('areas', datadir))
        self.events    = Events(data=self._load('events', datadir),
                                qualities=self.qualities,
                                locations=self.locations)

    def _load(self, entity, datadir=None):
        path = os.path.join(datadir or DATADIR,
                            'entities',
                            "{}_import.json".format(entity))
        log.debug("Opening data file for '%s': %s", entity, path)
        try:
            with open(path) as fd:
                # strict=False to allow tabs inside strings
                return json.load(fd, strict=False)
        except IOError as e:
            log.error("Could not load data file for '%s': %s", entity, e)
            return []




####################################################################################
# Import guard

if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as e:
        log.critical(e, exc_info=True)
        sys.exit(1)
    except KeyboardInterrupt:
        pass
