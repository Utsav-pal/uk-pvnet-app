"""
Tests for download_sat_data and preprocess_sat_data

1. Download just 5 minute sat
2. Download just 15 minute sat
3. Download 5 minute sat, then 15 minute sat
4. Download and process 5 minute
5. Download and process 15 minute
6. Download and process 5 and 15 minute, then use 15 minute

Note that I'm not sure these tests will work in parallel, due to files being saved in the same places
"""
import os
import tempfile
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest
import xarray as xr
import zarr

from pvnet_app.data.satellite import (
    check_for_constant_values,
    check_model_satellite_inputs_available,
    download_all_sat_data,
    extend_satellite_data_with_nans,
    preprocess_sat_data,
    interpolate_missing_satellite_timestamps,
    sat_5_path,
    sat_15_path,
    sat_path,
)


def save_to_zarr_zip(ds, filename):
    encoding = {"data": {"dtype": "int16"}}
    with zarr.ZipStore(filename) as store:
        ds.to_zarr(store, compute=True, mode="w", encoding=encoding, consolidated=True)


def check_timesteps(sat_path, expected_freq_mins):
    ds_sat = xr.open_zarr(sat_path)

    if not isinstance(expected_freq_mins, list):
        expected_freq_mins = [expected_freq_mins]

    dts = pd.to_datetime(ds_sat.time).diff()[1:]
    assert (np.isin(dts, [np.timedelta64(m, "m") for m in expected_freq_mins])).all(), dts


def test_download_sat_5_data(sat_5_data):
    """Download only the 5 minute satellite data"""

    # make temporary directory
    with tempfile.TemporaryDirectory() as tmpdirname:

        # Change to temporary working directory
        os.chdir(tmpdirname)

        # Make 5-minutely satellite data available
        save_to_zarr_zip(sat_5_data, filename="latest.zarr.zip")

        os.environ["SATELLITE_ZARR_PATH"] = "latest.zarr.zip"
        download_all_sat_data()

        # Assert that the file 'sat_5_path' exists
        assert os.path.exists(sat_5_path)
        assert not os.path.exists(sat_15_path)

        # Check the satellite data is 5-minutely
        check_timesteps(sat_5_path, expected_freq_mins=5)


def test_download_sat_15_data(sat_15_data):
    """Download only the 15 minute satellite data"""

    # make temporary directory
    with tempfile.TemporaryDirectory() as tmpdirname:

        # Change to temporary working directory
        os.chdir(tmpdirname)

        # Make 15-minutely satellite data available
        save_to_zarr_zip(sat_15_data, filename="latest_15.zarr.zip")

        os.environ["SATELLITE_ZARR_PATH"] = "latest.zarr.zip"

        download_all_sat_data()

        # Assert that the file 'sat_15_path' exists
        assert not os.path.exists(sat_5_path)
        assert os.path.exists(sat_15_path)

        # Check the satellite data is 15-minutely
        check_timesteps(sat_15_path, expected_freq_mins=15)


def test_download_sat_both_data(sat_5_data, sat_15_data):
    """Download 5 minute sat and 15 minute satellite data"""

    with tempfile.TemporaryDirectory() as tmpdirname:

        # Change to temporary working directory
        os.chdir(tmpdirname)

        # Make 5- and 15-minutely satellite data available
        save_to_zarr_zip(sat_5_data, filename="latest.zarr.zip")
        save_to_zarr_zip(sat_15_data, filename="latest_15.zarr.zip")

        os.environ["SATELLITE_ZARR_PATH"] = "latest.zarr.zip"

        download_all_sat_data()

        assert os.path.exists(sat_5_path)
        assert os.path.exists(sat_15_path)

        # Check this satellite data is 5-minutely
        check_timesteps(sat_5_path, expected_freq_mins=5)

        # Check this satellite data is 15-minutely
        check_timesteps(sat_15_path, expected_freq_mins=15)


def test_preprocess_sat_data(sat_5_data, test_t0):
    """Download and process only the 5 minute satellite data"""

    # make temporary directory
    with tempfile.TemporaryDirectory() as tmpdirname:

        # Change to temporary working directory
        os.chdir(tmpdirname)

        # Make 5-minutely satellite data available
        save_to_zarr_zip(sat_5_data, filename="latest.zarr.zip")

        os.environ["SATELLITE_ZARR_PATH"] = "latest.zarr.zip"
        download_all_sat_data()

        preprocess_sat_data(test_t0)

        # Check the satellite data is 5-minutely
        check_timesteps(sat_path, expected_freq_mins=5)


def test_preprocess_sat_15_data(sat_15_data, test_t0):
    """Download and process only the 15 minute satellite data"""

    # make temporary directory
    with tempfile.TemporaryDirectory() as tmpdirname:

        # Change to temporary working directory
        os.chdir(tmpdirname)

        # Make 15-minutely satellite data available
        save_to_zarr_zip(sat_15_data, filename="latest_15.zarr.zip")

        os.environ["SATELLITE_ZARR_PATH"] = "latest.zarr.zip"
        download_all_sat_data()

        preprocess_sat_data(test_t0)

        # We infill the satellite data to 5 minutes in the process step
        check_timesteps(sat_path, expected_freq_mins=5)


def test_preprocess_old_sat_5_data(sat_5_data_delayed, sat_15_data, test_t0):
    """Download and process 5 and 15 minute satellite data. Use the 15 minute data since the
    5 minute data is too delayed
    """

    # make temporary directory
    with tempfile.TemporaryDirectory() as tmpdirname:

        # Change to temporary working directory
        os.chdir(tmpdirname)

        save_to_zarr_zip(sat_5_data_delayed, filename="latest.zarr.zip")
        save_to_zarr_zip(sat_15_data, filename="latest_15.zarr.zip")

        os.environ["SATELLITE_ZARR_PATH"] = "latest.zarr.zip"
        download_all_sat_data()

        preprocess_sat_data(test_t0)

        # We infill the satellite data to 5 minutes in the process step
        check_timesteps(sat_path, expected_freq_mins=5)


def test_check_model_satellite_inputs_available(config_filename):

    t0 = datetime(2023,1,1)
    sat_datetime_1 = pd.date_range(t0 - timedelta(minutes=120), t0 - timedelta(minutes=5), freq="5min")
    sat_datetime_2 = pd.date_range(t0 - timedelta(minutes=120), t0 - timedelta(minutes=15), freq="5min")
    sat_datetime_3 = pd.date_range(t0 - timedelta(minutes=120), t0 - timedelta(minutes=35), freq="5min")
    sat_datetime_4 = pd.to_datetime([t for t in sat_datetime_1 if t!=t0-timedelta(minutes=30)])
    sat_datetime_5 = pd.to_datetime([t for t in sat_datetime_1 if t!=t0-timedelta(minutes=60)])

    assert check_model_satellite_inputs_available(config_filename, t0, sat_datetime_1)
    assert check_model_satellite_inputs_available(config_filename, t0, sat_datetime_2)
    assert not check_model_satellite_inputs_available(config_filename, t0, sat_datetime_3)
    assert not check_model_satellite_inputs_available(config_filename, t0, sat_datetime_4)
    assert not check_model_satellite_inputs_available(config_filename, t0, sat_datetime_5)


def test_extend_satellite_data_with_nans(sat_5_data):

    # make temporary directory
    with tempfile.TemporaryDirectory() as tmpdirname:

        # Change to temporary working directory
        os.chdir(tmpdirname)

        # save sat to zarr
        filename = "sat_5_data.zarr"
        sat_5_data.to_zarr(filename)

        time = sat_5_data.time.values
        t0 = pd.to_datetime(sat_5_data.time).max()
        extend_satellite_data_with_nans(t0=t0, satellite_data_path=filename)

        # load new file
        ds = xr.open_zarr(filename)
        assert (ds.time.values == time).all()


def test_extend_satellite_data_with_nans_over_3_hours(sat_5_data):

    # make temporary directory
    with tempfile.TemporaryDirectory() as tmpdirname:

        # Change to temporary working directory
        os.chdir(tmpdirname)

        # save sat to zarr
        filename = "sat_5_data.zarr"
        sat_5_data.to_zarr(filename)

        time = sat_5_data.time.values
        t0 = pd.to_datetime(sat_5_data.time).max() + pd.Timedelta(hours=4)
        extend_satellite_data_with_nans(t0=t0, satellite_data_path=filename)

        # load new file
        ds = xr.open_zarr(filename)
        assert len(time) + 3*12 == len(ds.time)
        assert ds.time.values[-1] == t0


def test_zeros_in_sat_data(sat_15_data_small, test_t0):
    """Check error is made if data has zeros"""

    # make temporary directory
    with tempfile.TemporaryDirectory() as tmpdirname:

        # Change to temporary working directory
        os.chdir(tmpdirname)

        # make half the values zeros
        sat_15_data_small.data[::2] = 0

        # Make 15-minutely satellite data available
        save_to_zarr_zip(sat_15_data_small, filename="latest.zarr.zip")

        os.environ["SATELLITE_ZARR_PATH"] = "latest.zarr.zip"
        download_all_sat_data()

        # check an error is made
        with pytest.raises(Exception):
            preprocess_sat_data(test_t0)


def test_remove_satellite_data(sat_15_data_small, test_t0):
    """Check error is made if data has nans"""
    # make temporary directory
    with tempfile.TemporaryDirectory() as tmpdirname:
        # Change to temporary working directory
        os.chdir(tmpdirname)

        # make half the values zeros
        sat_15_data_small = sat_15_data_small.copy(deep=True)
        sat_15_data_small.data[::2] = np.nan

        # Make 15-minutely satellite data available
        save_to_zarr_zip(sat_15_data_small, filename="latest.zarr.zip")

        os.environ["SATELLITE_ZARR_PATH"] = "latest.zarr.zip"
        download_all_sat_data()

        # check an error is made
        with pytest.raises(Exception):
            preprocess_sat_data(test_t0)


def test_interpolate_missing_satellite_timestamps(tmp_path):
    """Test that missing timestamps are interpolated"""

    # Create a 15 minutely dataset with missing timestamp
    t_start = "2023-01-01T00:00"
    t_end = "2023-01-01T03:00"
    times = np.delete(pd.date_range(start=t_start, end=t_end, freq="15min"), 1)

    ds = xr.DataArray(
        data=np.ones(times.shape),
        dims=["time"],
        coords=dict(time=times),
    ).to_dataset(name="data")
    ds.to_zarr(tmp_path)
    
    # This function loads data from sat_path, interpolates it adn saves it back to sat_path
    interpolate_missing_satellite_timestamps(max_gap=pd.Timedelta("15min"), zarr_path=tmp_path)

    # Reload the interpolated dataset
    ds_interp = xr.open_zarr(tmp_path)

    # The function interpolates to 5 minute intervals but will only interpolate between 
    # timestamps if there is less than 15 minutes between them. In this case, the 5 minute
    # intervals between the first two timestamps should not have been interpolated because
    # there is a 30 minute gap
    expected_times = pd.date_range(start=t_start, end=t_end, freq="5min")
    expected_times = [t for t in expected_times if not (times[0] < t < times[1])]

    assert (pd.to_datetime(ds_interp.time)==pd.to_datetime(expected_times)).all().item()

    assert (ds_interp.data.values==1).all().item()


def test_check_for_constant_values(sat_5_data):
    """Test check_for_constant_values"""

    # make temporary directory
    with tempfile.TemporaryDirectory() as tmpdirname:

        # Change to temporary working directory
        os.chdir(tmpdirname)

        # Make 5-minutely satellite data available
        sat_5_data.to_zarr("sat.zarr")

        check_for_constant_values()


def test_check_for_constant_values_zeros(sat_5_data):
    """Test check_for_constant_values error with lots of zeros"""

    sat_5_data = sat_5_data.copy(deep=True)

    sat_5_data['data'].values[:] = 0

    # make temporary directory
    with tempfile.TemporaryDirectory() as tmpdirname:
        # Change to temporary working directory
        os.chdir(tmpdirname)

        # Make 5-minutely satellite data available
        sat_5_data.to_zarr("sat.zarr")

        with pytest.raises(Exception):
            check_for_constant_values()


def test_check_for_constant_values_nans(sat_5_data):
    """Test check_for_constant_values, error with nans"""

    sat_5_data = sat_5_data.copy(deep=True)
    sat_5_data['data'].values[:] = np.nan

    # make temporary directory
    with tempfile.TemporaryDirectory() as tmpdirname:
        # Change to temporary working directory
        os.chdir(tmpdirname)

        # Make 5-minutely satellite data available
        sat_5_data.to_zarr("sat.zarr")

        with pytest.raises(Exception):
            check_for_constant_values(value=np.nan)
