import ee

ee.Initialize(project='afforestation-planner')

def calculate_ndvi():
    image = ee.Image("LANDSAT/LC08/C02/T1_L2/LC08_044034_20140318")

    ndvi = image.normalizedDifference(['SR_B5', 'SR_B4']).rename('NDVI')

    stats = ndvi.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=image.geometry(),
        scale=30,
        maxPixels=1e13
    )

    return stats.getInfo()
