import os
import time
import processing
from qgis.core import Qgis, QgsVectorLayer, QgsRasterLayer, QgsProject


power_values = [0,1,2,5]
resolution_values = [0.1, 1]
search_radius_values = [2, 4, 6, 8, 12]
base_output_folder_path = f"base folder path"
def get_statistics(output_raster_path, already_32 = False):
    if already_32 is True:
        converted_raster = QgsRasterLayer(output_raster_path,
                                          "converted_raster",
                                          "gdal")
        converted_raster_TRI_path = output_raster_path.replace(".tif", "_TRI.tif")
    elif already_32 is False:
        converted_raster_path = output_raster_path.replace(".tif", "_float32.tif")
        converted_raster_TRI_path = converted_raster_path.replace(".tif", "_TRI.tif")
        processing.run("gdal:translate",
                       {'INPUT': output_raster_path, 'TARGET_CRS': None,
                        'NODATA': None, 'COPY_SUBDATASETS': False,
                        'OPTIONS': '', 'EXTRA': '',
                        'DATA_TYPE': 6, 'OUTPUT': converted_raster_path})
        converted_raster = QgsRasterLayer(converted_raster_path,
                                          "converted_raster",
                                          "gdal")
    else:
        return
    QgsProject.instance().addMapLayer(converted_raster)

    # First part: Absolute pixel-by-pixel difference.
    expression = f'\' "etopo@1" - "converted_raster@1" \''
    difference_output_path = output_raster_path.replace(".tif", "_D.tif")
    processing.run("native:rastercalc", {
        'LAYERS': [etopo.source(), converted_raster.source()],
        'EXPRESSION': expression, 'EXTENT': None, 'CELL_SIZE': resolution_value, 'CRS': None,
        'OUTPUT': difference_output_path})
    histo_output_path = output_raster_path.replace(".tif", "_H.html")
    processing.run("qgis:rasterlayerhistogram", {
        'INPUT': difference_output_path,
        'BAND': 1, 'BINS': 1000, 'OUTPUT': histo_output_path})
    stats_output_path = output_raster_path.replace(".tif", "_S.html")
    processing.run("native:rasterlayerstatistics", {
        'INPUT': difference_output_path,
        'BAND': 1,
        'OUTPUT_HTML_FILE': stats_output_path})

    # Second part: Terrain Ruggedness Index (TRI) pixel-by-pixel difference.
    processing.run("gdal:triterrainruggednessindex", {
        'INPUT': converted_raster.source(),
        'BAND': 1, 'COMPUTE_EDGES': False, 'OPTIONS': '',
        'OUTPUT': converted_raster_TRI_path})
    converted_raster_TRI = QgsRasterLayer(converted_raster_TRI_path,
                                          "converted_raster_TRI",
                                          "gdal")
    QgsProject.instance().addMapLayer(converted_raster_TRI)
    expression_TRI = f'\' "etopo_TRI@1" - "converted_raster_TRI@1" \''
    difference_TRI_output_path = output_raster_path.replace(".tif", "_D_TRI.tif")
    processing.run("native:rastercalc", {
        'LAYERS': [etopo_TRI.source(), converted_raster_TRI.source()],
        'EXPRESSION': expression_TRI, 'EXTENT': None, 'CELL_SIZE': resolution_value, 'CRS': None,
        'OUTPUT': difference_TRI_output_path})
    TRI_histo_output_path = output_raster_path.replace(".tif", "_H_TRI.html")
    processing.run("qgis:rasterlayerhistogram", {
        'INPUT': difference_TRI_output_path,
        'BAND': 1, 'BINS': 1000, 'OUTPUT': TRI_histo_output_path})
    TRI_stats_output_path = output_raster_path.replace(".tif", "_S_TRI.html")
    processing.run("native:rasterlayerstatistics", {
        'INPUT': difference_TRI_output_path,
        'BAND': 1,
        'OUTPUT_HTML_FILE': TRI_stats_output_path})

for resolution_value in resolution_values:
    input_nodes_path = f"Input/all_nodes_resampled_r{resolution_value}.geojson"
    input_nodes = QgsVectorLayer(input_nodes_path, "Input Nodes", "ogr")
    etopo_path = f"Input/ETOPO_2022_global_ice_r{resolution_value}.tif"
    etopo = QgsRasterLayer(etopo_path, "etopo", "gdal")
    QgsProject.instance().addMapLayer(etopo)
    etopo_TRI_path = etopo_path.replace(".tif", "_TRI.tif")
    etopo_TRI = QgsRasterLayer(etopo_TRI_path, "etopo_TRI", "gdal")
    QgsProject.instance().addMapLayer(etopo_TRI)
    #########################################################################################################################################################################
    #IDW PART.
    #########################################################################################################################################################################
    method = "IDW"
    #1: Native QGIS
    for power_value in power_values:
        start_time = time.time()
        output_raster_path = os.path.join(base_output_folder_path, method,f"01_QGIS_p{power_value}_r{resolution_value}.tif")
        processing.run("qgis:idwinterpolation", {
            'INTERPOLATION_DATA': f'{input_nodes.source()}::~::0::~::0::~::0',
            'DISTANCE_COEFFICIENT': power_value,
            'EXTENT': '-180.000000000,180.000000000,-90.000000000,90.000000000 [EPSG:4326]',
            'PIXEL_SIZE': resolution_value,
            'OUTPUT': output_raster_path})
        get_statistics(output_raster_path)
        elapsed_time = time.time() - start_time
        output_file_path = os.path.join(base_output_folder_path, "time.txt")
        with open(output_file_path, 'a') as file:
            if file.tell() == 0:
                file.write("raster_name, processing_time\n")
            file.write(f"{output_raster_path}, {elapsed_time}\n")
    #2: GDAL
    for power_value in power_values:
        for search_radius_value in search_radius_values:
            start_time = time.time()
            output_raster_path = os.path.join(base_output_folder_path, method, f"02_GDAL_p{power_value}_r{resolution_value}_R{search_radius_value}.tif")
            processing.run("gdal:gridinversedistancenearestneighbor",
                           {'DATA_TYPE': 5,
                            'EXTRA': f'-txe {-180} {180} -tye {-90} {90} -tr {resolution_value} {resolution_value}',
                            'INPUT': input_nodes.source(), 'MAX_POINTS': 12, 'MIN_POINTS': 0,
                            'NODATA': 0, 'OPTIONS': '', 'OUTPUT': output_raster_path,
                            'POWER': power_value, 'RADIUS': search_radius_value,
                            'SMOOTHING': 0, 'Z_FIELD': 'Z'
                            })
            get_statistics(output_raster_path)
            elapsed_time = time.time() - start_time
            output_file_path = os.path.join(base_output_folder_path, "time.txt")
            with open(output_file_path, 'a') as file:
                if file.tell() == 0:
                    file.write("raster_name, processing_time\n")
                file.write(f"{output_raster_path}, {elapsed_time}\n")
    #3: SAGA
    for power_value in power_values:
        for search_radius_value in search_radius_values:
            start_time = time.time()
            output_raster_path = os.path.join(base_output_folder_path, method, f"03_SAGA_p{power_value}_r{resolution_value}_R{search_radius_value}.tif")
            output_summary_path = output_raster_path.replace(".tif", "_SUM.dbf")
            output_residuals_path =  output_raster_path.replace(".tif", "_RES.dbf")
            processing.run("sagang:inversedistanceweightedinterpolation", {
                'POINTS': input_nodes.source(),
                'FIELD': 'Z',
                'CV_METHOD': 1,
                'CV_SUMMARY': output_summary_path,
                'CV_RESIDUALS': output_residuals_path,
                'CV_SAMPLES': 10,
                'TARGET_USER_XMIN TARGET_USER_XMAX TARGET_USER_YMIN TARGET_USER_YMAX': '-180.000000000,180.000000000,-90.000000000,90.000000000 [EPSG:4326]',
                'TARGET_USER_SIZE': resolution_value,
                'TARGET_USER_FITS': 1,
                'TARGET_OUT_GRID': output_raster_path,
                'SEARCH_RANGE': 0,
                'SEARCH_RADIUS': search_radius_value,
                'SEARCH_POINTS_ALL': 1,
                'SEARCH_POINTS_MIN': 1,
                'SEARCH_POINTS_MAX': 12,
                'DW_WEIGHTING': 1,
                'DW_IDW_POWER': power_value,
                'DW_BANDWIDTH': 1})
            get_statistics(output_raster_path)
            elapsed_time = time.time() - start_time
            output_file_path = os.path.join(base_output_folder_path, "time.txt")
            with open(output_file_path, 'a') as file:
                if file.tell() == 0:
                    file.write("raster_name, processing_time\n")
                file.write(f"{output_raster_path}, {elapsed_time}\n")
    #4: GRASS
    for power_value in power_values:
        start_time = time.time()
        output_raster_path = os.path.join(base_output_folder_path, method, f"04_GRASS_p{power_value}_r{resolution_value}.tif")
        processing.run("grass:v.surf.idw", {
            'input': input_nodes.source(),
            'npoints': 12, 'power': power_value, 'column': 'Z', '-n': False, 'output': output_raster_path,
            'GRASS_REGION_PARAMETER': '-180.000000000,180.000000000,-90.000000000,90.000000000 [EPSG:4326]',
            'GRASS_REGION_CELLSIZE_PARAMETER': resolution_value, 'GRASS_RASTER_FORMAT_OPT': '', 'GRASS_RASTER_FORMAT_META': '',
            'GRASS_SNAP_TOLERANCE_PARAMETER': -1, 'GRASS_MIN_AREA_PARAMETER': 0.0001})
        get_statistics(output_raster_path)
        elapsed_time = time.time() - start_time
        output_file_path = os.path.join(base_output_folder_path, "time.txt")
        with open(output_file_path, 'a') as file:
            if file.tell() == 0:
                file.write("raster_name, processing_time\n")
            file.write(f"{output_raster_path}, {elapsed_time}\n")
    #5: ArcGIS
    #(Only post-processing is done here, as the interpolation is done in ArcGIS)
    for power_value in power_values:
        for search_radius_value in search_radius_values:
            start_time = time.time()
            output_raster_path = os.path.join(base_output_folder_path, method, f"05_ArcGIS_r{resolution_value}_p{power_value}_R{search_radius_value}.tif")
            get_statistics(output_raster_path, True)
            elapsed_time = time.time() - start_time
            output_file_path = os.path.join(base_output_folder_path, "time.txt")
            with open(output_file_path, 'a') as file:
                if file.tell() == 0:
                    file.write("raster_name, processing_time\n")
                file.write(f"{output_raster_path}, {elapsed_time}\n")
    #########################################################################################################################################################################
    #IDW NN PART.
    #########################################################################################################################################################################
    method = "IDW_NN"
    #1: GDAL
    for power_value in power_values:
        for search_radius_value in search_radius_values:
            start_time = time.time()
            output_raster_path = os.path.join(base_output_folder_path, method, f"01_GDAL_p{power_value}_r{resolution_value}_R{search_radius_value}.tif")
            processing.run("gdal:gridinversedistancenearestneighbor",
                           {'DATA_TYPE': 5,
                            'EXTRA': f'-txe {-180} {180} -tye {-90} {90} -tr {resolution_value} {resolution_value}',
                            'INPUT': input_nodes.source(), 'MAX_POINTS': 12,
                            'MIN_POINTS': 0,
                            'NODATA': 0,
                            'OPTIONS': '',
                            'OUTPUT': output_raster_path,
                            'POWER': power_value,
                            'RADIUS': search_radius_value,
                            'SMOOTHING': 0.,
                            'Z_FIELD': 'Z'
                            })
            get_statistics(output_raster_path)
            elapsed_time = time.time() - start_time
            output_file_path = os.path.join(base_output_folder_path, "time.txt")
            with open(output_file_path, 'a') as file:
                if file.tell() == 0:
                    file.write("raster_name, processing_time\n")
                file.write(f"{output_raster_path}, {elapsed_time}\n")
    #########################################################################################################################################################################
    # TIN PART.
    #########################################################################################################################################################################
    method = "TIN"
    #1: QGIS
    start_time = time.time()
    output_raster_path = os.path.join(base_output_folder_path, method, f"01_QGIS_r{resolution_value}.tif")
    processing.run("qgis:tininterpolation", {
        'INTERPOLATION_DATA': f'{input_nodes.source()}::~::0::~::0::~::0',
        'METHOD': 0,
        'EXTENT': '-180.000000000,180.000000000,-90.000000000,90.000000000 [EPSG:4326]',
        'PIXEL_SIZE': resolution_value,
        'OUTPUT': output_raster_path})
    get_statistics(output_raster_path)
    elapsed_time = time.time() - start_time
    output_file_path = os.path.join(base_output_folder_path, "time.txt")
    with open(output_file_path, 'a') as file:
        if file.tell() == 0:
            file.write("raster_name, processing_time\n")
        file.write(f"{output_raster_path}, {elapsed_time}\n")
    #########################################################################################################################################################################
    # NN PART.
    #########################################################################################################################################################################
    method = "NN"
    #1:SAGA
    start_time = time.time()
    output_raster_path = os.path.join(base_output_folder_path, method, f"01_SAGA_r{resolution_value}.tif")
    output_summary_path = output_raster_path.replace(".tif", "_SUM.dbf")
    output_residuals_path = output_raster_path.replace(".tif", "_RES.dbf")
    processing.run("sagang:nearestneighbour",
                   {'POINTS': input_nodes.source(),
                    'FIELD': 'Z',
                    'CV_METHOD': 1,
                    'CV_SUMMARY': output_summary_path,
                    'CV_RESIDUALS': output_residuals_path,
                    'CV_SAMPLES': 10,
                    'TARGET_USER_XMIN TARGET_USER_XMAX TARGET_USER_YMIN TARGET_USER_YMAX': '-180.000000000,180.000000000,-90.000000000,90.000000000 [EPSG:4326]',
                    'TARGET_USER_SIZE': resolution_value,
                    'TARGET_USER_FITS': 1,
                    'TARGET_OUT_GRID': output_raster_path
                    })
    get_statistics(output_raster_path)
    elapsed_time = time.time() - start_time
    output_file_path = os.path.join(base_output_folder_path, "time.txt")
    with open(output_file_path, 'a') as file:
        if file.tell() == 0:
            file.write("raster_name, processing_time\n")
        file.write(f"{output_raster_path}, {elapsed_time}\n")
    #2: GDAL
    for search_radius_value in search_radius_values:
        start_time = time.time()
        output_raster_path = os.path.join(base_output_folder_path, method, f"02_GDAL_r{resolution_value}_R{search_radius_value}.tif")
        processing.run("gdal:gridnearestneighbor",
                       {'INPUT': input_nodes.source(),
                        'Z_FIELD': 'Z',
                        'RADIUS_1': search_radius_value,
                        'RADIUS_2': search_radius_value,
                        'ANGLE': 0,
                        'NODATA': 0,
                        'OPTIONS': '',
                        'EXTRA': f'-txe {-180} {180} -tye {-90} {90} -tr {resolution_value} {resolution_value}',
                        'DATA_TYPE': 5,
                        'OUTPUT': output_raster_path
                        })
        get_statistics(output_raster_path)
        elapsed_time = time.time() - start_time
        output_file_path = os.path.join(base_output_folder_path, "time.txt")
        with open(output_file_path, 'a') as file:
            if file.tell() == 0:
                file.write("raster_name, processing_time\n")
            file.write(f"{output_raster_path}, {elapsed_time}\n")

    #########################################################################################################################################################################
    # TOPO TO RASTER PART.
    #########################################################################################################################################################################
    method = "TopotoRaster"
    #1: ArcGIS
    start_time = time.time()
    # (Only post-processing is done here, as the interpolation is done in ArcGIS)
    output_raster_path = os.path.join(base_output_folder_path, method, f"01_ArcGIS_r{resolution_value}.tif")
    get_statistics(output_raster_path, True)
    elapsed_time = time.time() - start_time
    output_file_path = os.path.join(base_output_folder_path, "time.txt")
    with open(output_file_path, 'a') as file:
        if file.tell() == 0:
            file.write("raster_name, processing_time\n")
        file.write(f"{output_raster_path}, {elapsed_time}\n")
    #########################################################################################################################################################################
    # KRIGING PART.
    #########################################################################################################################################################################
    method = "Kriging"
    #1: ArcGIS
    #(Only post-processing is done here, as the interpolation is done in ArcGIS)
    for search_radius_value in search_radius_values:
        start_time = time.time()
        output_raster_path = os.path.join(base_output_folder_path, method, f"01_ArcGIS_r{resolution_value}_R{search_radius_value}.tif")
        get_statistics(output_raster_path, True)
        elapsed_time = time.time() - start_time
        output_file_path = os.path.join(base_output_folder_path, "time.txt")
        with open(output_file_path, 'a') as file:
            if file.tell() == 0:
                file.write("raster_name, processing_time\n")
            file.write(f"{output_raster_path}, {elapsed_time}\n")
    #########################################################################################################################################################################
    # NATURAL NEIGHBOUR PART.
    #########################################################################################################################################################################
    method = "NatN"
    #1: ArcGIS
    start_time = time.time()
    #(Only post-processing is done here, as the interpolation is done in ArcGIS)
    output_raster_path = os.path.join(base_output_folder_path,method, f"01_ArcGIS_r{resolution_value}.tif")
    get_statistics(output_raster_path, True)
    elapsed_time = time.time() - start_time
    output_file_path = os.path.join(base_output_folder_path, "time.txt")
    with open(output_file_path, 'a') as file:
        if file.tell() == 0:
            file.write("raster_name, processing_time\n")
        file.write(f"{output_raster_path}, {elapsed_time}\n")