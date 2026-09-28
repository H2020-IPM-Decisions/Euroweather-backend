import hashlib
import os

import numpy as np
from eccodes import (
    codes_clone,
    codes_get,
    codes_get_array,
    codes_grib_new_from_file,
    codes_release,
    codes_set,
    codes_set_values,
    codes_write,
)
from scipy.spatial import cKDTree


def _read_grib(path):
    with open(path, "rb") as source:
        handle = codes_grib_new_from_file(source)
        if handle is None:
            raise ValueError(f"No GRIB message found in {path}")
        try:
            return codes_get_array(handle, "values"), codes_get(handle, "uuidOfHGrid")
        finally:
            codes_release(handle)


def _unit_vectors(latitudes, longitudes):
    latitudes = np.deg2rad(latitudes)
    longitudes = np.deg2rad(longitudes)
    cos_latitudes = np.cos(latitudes)
    return np.column_stack(
        (
            cos_latitudes * np.cos(longitudes),
            cos_latitudes * np.sin(longitudes),
            np.sin(latitudes),
        )
    )


class IconEuRemapper:
    def __init__(
        self, latitude_path, longitude_path, cache_dir, target_resolution=0.0625
    ):
        if target_resolution <= 0:
            raise ValueError("Target resolution must be greater than zero")

        source_latitudes, latitude_grid_id = _read_grib(latitude_path)
        source_longitudes, longitude_grid_id = _read_grib(longitude_path)
        if latitude_grid_id != longitude_grid_id:
            raise ValueError("ICON-EU CLAT and CLON use different grids")
        if source_latitudes.shape != source_longitudes.shape:
            raise ValueError("ICON-EU CLAT and CLON have different sizes")

        self.grid_id = latitude_grid_id
        self.source_size = source_latitudes.size
        self.target_resolution = target_resolution
        longitude_start = np.ceil(
            source_longitudes.min() / target_resolution
        ).astype(int)
        longitude_end = np.floor(
            source_longitudes.max() / target_resolution
        ).astype(int)
        latitude_start = np.floor(
            source_latitudes.max() / target_resolution
        ).astype(int)
        latitude_end = np.ceil(
            source_latitudes.min() / target_resolution
        ).astype(int)
        self.target_longitudes = (
            np.arange(longitude_start, longitude_end + 1) * target_resolution
        )
        self.target_latitudes = (
            np.arange(latitude_start, latitude_end - 1, -1) * target_resolution
        )
        if self.target_longitudes.size == 0 or self.target_latitudes.size == 0:
            raise ValueError("ICON-EU coordinates do not define a targetable domain")

        target_definition = (
            f"{target_resolution}:"
            f"{self.target_longitudes[0]}:{self.target_longitudes[-1]}:"
            f"{self.target_latitudes[0]}:{self.target_latitudes[-1]}"
        )
        target_id = hashlib.sha256(target_definition.encode()).hexdigest()[:12]
        cache_path = os.path.join(
            cache_dir, f"icon_eu_nearest_{latitude_grid_id}_{target_id}.npy"
        )
        if os.path.isfile(cache_path):
            self.indices = np.load(cache_path)
        else:
            source_points = _unit_vectors(source_latitudes, source_longitudes)
            target_longitudes, target_latitudes = np.meshgrid(
                self.target_longitudes, self.target_latitudes
            )
            target_points = _unit_vectors(
                target_latitudes.ravel(), target_longitudes.ravel()
            )
            _, self.indices = cKDTree(source_points).query(
                target_points, workers=-1
            )
            self.indices = self.indices.astype(np.int32)
            np.save(cache_path, self.indices)

        expected_size = self.target_longitudes.size * self.target_latitudes.size
        if self.indices.shape != (expected_size,):
            raise ValueError(f"Invalid cached ICON-EU mapping in {cache_path}")
        if self.indices.min() < 0 or self.indices.max() >= self.source_size:
            raise ValueError(f"Out-of-range ICON-EU mapping in {cache_path}")

    def remap(self, input_path, output_path):
        with open(input_path, "rb") as source:
            original = codes_grib_new_from_file(source)
            if original is None:
                raise ValueError(f"No GRIB message found in {input_path}")
            try:
                grid_id = codes_get(original, "uuidOfHGrid")
                if grid_id != self.grid_id:
                    raise ValueError(
                        f"{input_path} uses ICON grid {grid_id}; "
                        f"expected {self.grid_id}"
                    )
                values = codes_get_array(original, "values")
                if values.size != self.source_size:
                    raise ValueError(
                        f"{input_path} has {values.size} cells; "
                        f"expected {self.source_size}"
                    )
                output = codes_clone(original)
            finally:
                codes_release(original)

        temporary_path = f"{output_path}.tmp"
        try:
            grid_definition = {
                "gridType": "regular_ll",
                "Ni": self.target_longitudes.size,
                "Nj": self.target_latitudes.size,
                "latitudeOfFirstGridPointInDegrees": self.target_latitudes[0],
                "longitudeOfFirstGridPointInDegrees": self.target_longitudes[0],
                "latitudeOfLastGridPointInDegrees": self.target_latitudes[-1],
                "longitudeOfLastGridPointInDegrees": self.target_longitudes[-1],
                "iDirectionIncrementInDegrees": self.target_resolution,
                "jDirectionIncrementInDegrees": self.target_resolution,
                "iScansNegatively": 0,
                "jScansPositively": 0,
                "jPointsAreConsecutive": 0,
                "alternativeRowScanning": 0,
            }
            for key, value in grid_definition.items():
                codes_set(output, key, value)
            codes_set_values(output, values[self.indices])

            with open(temporary_path, "wb") as target:
                codes_write(output, target)
            os.replace(temporary_path, output_path)
        finally:
            codes_release(output)
            if os.path.isfile(temporary_path):
                os.unlink(temporary_path)
