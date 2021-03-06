# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from nextgisweb.component import Component


class OgrExportComponent(Component):
    identity = 'ogr_export'

    def initialize(self):
        pass

    def setup_pyramid(self, config):
        from . import view  # NOQA
        view.setup_pyramid(self, config)


def pkginfo():
    return dict(
        components=dict(
            ogr_export="nextgisweb_ogr_export"
        )
    )


def amd_packages():
    return ()
