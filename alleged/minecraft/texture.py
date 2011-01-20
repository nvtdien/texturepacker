#!/usr/bin/env python
# encoding: utf-8
"""
texture.py

Created by Damian Cugley on 2011-01-12.
Copyright (c) 2011 __MyCompanyName__. All rights reserved.
"""

import sys
import os
from zipfile import ZipFile, ZIP_DEFLATED
from StringIO import StringIO
from base64 import b64decode
import Image

class ResourceBase(object):
    def __init__(self, name):
        self.name = name

    def get_bytes(self):
        raise NotImplemented('{0}.get_bytes'.format(self.__class__.__name))

    def get_image(self):
        raise NotImplemented('{0}.get_image'.format(self.__class__.__name))


class TextResource(ResourceBase):
    """A document whose content is a literal string."""
    def __init__(self, name, content):
        super(TextResource, self).__init__(name)
        self.content = content

    def get_content(self):
        return self.content

    def get_bytes(self):
        """Get the byte sequence that will go in the ZIP archive"""
        return self.get_content().encode('UTF-8')

class RecipePack(object):
    """Represents a texture pack."""
    def __init__(self, label, desc):
        self.label = label
        self.desc = desc
        self.resources = {}

        self.add_resource(TextResource('pack.txt', u'{label}\n{desc}'.format(label=label, desc=desc)))

    def add_resource(self, resource):
        self.resources[resource.name] = resource

    def get_resource(self, name):
        return self.resources[name]

    def write_to(self, strm):
        with ZipFile(strm, 'w', ZIP_DEFLATED) as zip:
            for name, resource in sorted(self.resources.items()):
                zip.writestr(name, resource.get_bytes())


class SourcePack(object):
    def __init__(self, zip_data):
        self.zip = ZipFile(zip_data)
        self.resources = {}

    def __del__(self):
        self.zip.close()

    def get_resource(self, name):
        res = self.resources.get(name)
        if res:
            return res
        if name.endswith('.txt'):
            text = self.zip.read(name).decode('UTF-8')
            res = TextResource(name, text)
        else:
            res = SourceResource(self, name)
        self.resources[name] = res
        return res

    def get_resource_bytes(self, name):
        return self.zip.read(name)

    @property
    def label(self):
        res = self.get_resource('pack.txt')
        return res.get_content().split('\n', 1)[0]

    @property
    def desc(self):
        res = self.get_resource('pack.txt')
        return res.get_content().split('\n', 1)[1]

class SourceResource(ResourceBase):
    def __init__(self, source, name):
        self.source = source
        self.name = name
        self.bytes = None
        self.image = None

    def get_bytes(self):
        if self.bytes is None:
            self.bytes = self.source.get_resource_bytes(self.name)
        return self.bytes

    def get_image(self):
        if self.image is None:
            strm = StringIO(self.get_bytes())
            self.image = Image.open(strm)
        return self.image

class Map(object):
        pass

class GridMap(Map):
    def __init__(self, image_size, cell_size, names):
        """Create a grid map with this size and names.

        Arguments --
            image_size -- pair (WIDTH, HEIGHT) -- size of the overall image
            cell_size -- pair (WIDTH, HEIGHT) -- size of cells within the image
                The image width should be a multiple of the cell width
                and similarly for the heights.
            names --
                List of names, in order left to right, top to bottom.
        """
        self.cell_wd, self.cell_ht = cell_size
        self.im_wd, self.im_ht = image_size
        self.nx, self.ny = self.im_wd // self.cell_wd, self.im_ht // self.cell_ht

        self.names = names

    def get_box(self, name):
        i = self.names.index(name)
        u, v = i % self.nx, i // self.ny
        return (self.cell_wd * u, self.cell_ht * v, self.cell_wd * (u + 1), self.cell_ht * (v + 1))

class CompositeResource(ResourceBase):
    def __init__(self, name, base_res, base_map):
        super(CompositeResource, self).__init__(name)
        self.res = base_res
        self.map = base_map
        self.replacements = []
        self.image = None

    def replace(self, res, map, cells):
        self.replacements.append((res, map, cells))
        self.im = None
        self.bytes = None

    def _calc(self):
        im = self.res.get_image().copy()
        for src_res, src_map, cells in self.replacements:
            for dst_name, src_name in cells.iteritems():
                dst_box = self.map.get_box(dst_name)
                src_box = src_map.get_box(src_name)
                src_im = src_res.get_image().crop(src_box)
                im.paste(src_im, dst_box)
        self.image = im

    def get_bytes(self):
        if self.bytes is None:
            if self.image is None:
                self._calc()
            strm = StringIO()
            self.image.save(strm, 'PNG', optimize=True)
            self.bytes = strm.getvalue()
        return self.bytes

class Mixer(object):
    def __init__(self):
        self.packs = {}

    def add_pack(self, name, pack):
        self.packs[name] = pack

    def make(self, recipe):
        new_pack = RecipePack(recipe['label'], recipe['desc'])
        for ingredient in recipe['mix']:
            pack = self.packs[ingredient['pack']]
            for file_spec in ingredient['files']:
                res_name = file_spec
                res = pack.get_resource(res_name)
                new_pack.add_resource(res)
        return new_pack
