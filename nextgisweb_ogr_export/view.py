# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import tempfile
from shutil import rmtree
from sys import path
from zipfile import ZipFile, ZIP_DEFLATED

import codecs
import json
import subprocess

import geojson
import os
from osgeo import ogr
from pyramid.response import Response, FileResponse
import pyramid.httpexceptions as exc
from nextgisweb import layer
from nextgisweb.feature_layer import IFeatureLayer
from nextgisweb.feature_layer.view import ComplexEncoder
from nextgisweb.resource import resource_factory, DataScope
from nextgisweb.vector_layer import VectorLayer


def setup_pyramid(comp, config):

    config.add_route(
        'feature_layer.feature.item', '/api/resource/{id}/ogr_export/{fmt}',
        factory=resource_factory) \
        .add_view(ogr_export, context=IFeatureLayer, request_method='GET')


def ogr_export(resource, request):
    request.resource_permission(DataScope.read)

    # check
    fmt = request.matchdict['fmt']
    if fmt not in get_driver_names():
        raise exc.HTTPInternalServerError

    #create temporary dir
    zip_dir = tempfile.mkdtemp()

    # save layers to geojson (FROM FEATURE_LAYER)
    json_path = path.join(zip_dir, '%s.%s' % (layer.display_name, 'json'))
    _save_resource_to_file(layer, json_path, single_geom=fmt == 'csv')

    export_path = path.join(zip_dir, '%s.%s' % (layer.display_name, fmt))
    _convert_json(json_path, export_path, fmt)
    # remove json
    os.remove(json_path.encode('utf-8'))


    with tempfile.NamedTemporaryFile(delete=True) as temp_file:
        # write archive
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
        # response.content_disposition = 'attachment; filename="%s"' % focl_resource.display_name.encode('utf-8')
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
    # get ext


    # create
    params = ['ogr2ogr',
              '-f', 'KML',
              out_file_path.encode('utf-8'),
              in_file_path.encode('utf-8'),
              '-s_srs', 'EPSG:3857',
              '-t_srs', 'EPSG:4326',
             ]

    if fmt == 'csv':
        params.extend(['-lco', 'GEOMETRY=AS_XY'])

    subprocess.check_call(params)


def get_driver_names():
    formats = set()

    for i in range(ogr.GetDriverCount()):
        driver = ogr.GetDriver(i)
        formats.append(driver.GetName())

    return formats
