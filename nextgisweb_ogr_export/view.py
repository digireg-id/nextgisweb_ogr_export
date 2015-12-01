# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import subprocess
import tempfile
from shutil import rmtree
from zipfile import ZipFile, ZIP_DEFLATED

import codecs
import geojson
import os
import pyramid.httpexceptions as exc
from os import path
from osgeo import ogr
from pyramid.response import FileResponse

from nextgisweb import layer
from nextgisweb.feature_layer import IFeatureLayer
from nextgisweb.feature_layer.view import ComplexEncoder
from nextgisweb.resource import resource_factory, DataScope

REPLACEMENTS = {
    'esri shapefile': 'shp',
    'mapinfo file': 'tab',
    'geoconcept': 'gxt',
    'interlis 1': 'itf',
    'interlis 2': 'xtf',
    'gpstrackmaker': 'gtm',

    #'sqlite': 'sqlite',
    #'splite': 'splite',
    #'pcidsk'
}

EXCLUDED_DRIVERS = [
    'htf',
    'openair',
    'segy',
    'arcgen',
    'aeronavfaa',
    'mssqlspatial',
    'gme',
    'cartodb',
    'mysql',
    'edigeo',
    'uk .ntf',
    's57',
    'nas',
    'idrisi',
    'memory',
    'xplane',
    'rec',
    'couchdb',
    'vrt',
    'avcbin',
    'walk',
    'vfk',
    'tiger',
    'segukooa',
    'pds',
    'wfs',
    'openfilegdb',
    'avce00',
    'geomedia',
    'ogdi',
    'postgresql',
    'sua',
    'gpsbabel', #???
    'svg',
    'odbc',
    'dods',
    'elasticsearch',
    'osm',
    'xls',
    'sdts',
]

ADDITIONAL_FLAGS = {
    'csv': ['-lco', 'GEOMETRY=AS_XY'],
    'shp': ['-lco', 'ENCODING=UTF-8']
}


def setup_pyramid(comp, config):

    config.add_route(
        'feature_layer.ogr_export.export', '/resource/{id}/ogr_export/{fmt}',
        factory=resource_factory) \
        .add_view(ogr_export, context=IFeatureLayer, request_method='GET')


def ogr_export(resource, request):
    request.resource_permission(DataScope.read)

    # check
    fmt = request.matchdict['fmt']
    if fmt not in get_driver_names():
        raise exc.HTTPInternalServerError('Unsupported format!')

    #create temporary dir
    zip_dir = tempfile.mkdtemp()

    # save layers to geojson (FROM FEATURE_LAYER)
    json_path = path.join(zip_dir, '%s.%s' % (resource.display_name, 'json'))
    _save_resource_to_file(resource, json_path, single_geom=fmt == 'csv')

    # convert
    export_path = path.join(zip_dir, '%s.%s' % (resource.display_name, fmt))
    _convert_json(json_path, export_path, fmt)

    # remove json
    os.remove(json_path.encode('utf-8'))

    # write archive
    with tempfile.NamedTemporaryFile(delete=True) as temp_file:
        zip_file = ZipFile(temp_file, mode="w", compression=ZIP_DEFLATED)
        zip_subpath = resource.display_name + '/'

        for file_name in os.listdir(zip_dir):
            src_file = path.join(zip_dir, file_name)
            zip_file.write(src_file, (zip_subpath+unicode(file_name, 'utf-8')).encode('cp866'))
        zip_file.close()

        # remove temporary dir
        rmtree(zip_dir)

        # send
        temp_file.seek(0, 0)
        response = FileResponse(
            path.abspath(temp_file.name),
            content_type=bytes('application/zip'),
            request=request
        )
        response.content_disposition = 'attachment; filename="%s.%s.zip"' % (resource.display_name.encode('utf-8'), fmt)
        return response


def _save_resource_to_file(vector_resource, file_path, single_geom=False):

    class CRSProxy(object):
        def __init__(self, query):
            self.query = query

        @property
        def __geo_interface__(self):
            result = self.query.__geo_interface__
            result['crs'] = dict(type='name', properties=dict(
                name='EPSG:3857'))
            return result

    query = vector_resource.feature_query()
    query.geom(single_part=single_geom)
    result = CRSProxy(query())

    gj = geojson.dumps(result, ensure_ascii=False, cls=ComplexEncoder)
    with codecs.open(file_path.encode('utf-8'), 'w', encoding='utf-8') as f:
        f.write(gj)



def _convert_json(in_file_path, out_file_path, fmt):
    fmt_norm = fmt
    if fmt in REPLACEMENTS.values():
        for k,v in REPLACEMENTS.iteritems():
            if v == fmt:
                fmt_norm = k
                break

    params = ['ogr2ogr',
              '-f', fmt_norm,
              out_file_path.encode('utf-8'),
              in_file_path.encode('utf-8'),
              '-s_srs', 'EPSG:3857',
              '-t_srs', 'EPSG:4326',
             ]

    if fmt in ADDITIONAL_FLAGS.keys():
        params.extend(ADDITIONAL_FLAGS[fmt])

    subprocess.check_call(params)

def get_driver_names():
    formats = set()

    for i in range(ogr.GetDriverCount()):
        driver = ogr.GetDriver(i)
        name = driver.GetName().lower()
        if name in REPLACEMENTS.keys():
            name = REPLACEMENTS[name]
        formats.add(name)

    return formats
