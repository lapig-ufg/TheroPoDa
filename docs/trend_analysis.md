
# Trend Analysis Module

This module includes functionalities for trend analysis.

## Overview

The `trend_analysis` module provides functions to analyze trends in time series data.

## Functions

### `calculate_moving_average(data, window_size)`

Calculates the moving average of a time series.

#### Parameters

- `data` (list of float): The time series data.
- `window_size` (int): The window size for the moving average calculation.

#### Returns

- `list of float`: The time series of moving averages.

#### Example Usage

```python
from trend_analysis import calculate_moving_average

data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
moving_average = calculate_moving_average(data, window_size=3)
print(moving_average)  # Output: [2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
```

### `detect_trend(data)`

Detects the trend in a time series.

#### Parameters

- `data` (list of float): The time series data.

#### Returns

- `str`: The detected trend ('upward', 'downward', 'stable').

#### Example Usage

```python
from trend_analysis import detect_trend

data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
trend = detect_trend(data)
print(trend)  # Output: upward
```

### `forecast(data, periods)`

Forecasts future values of a time series.

#### Parameters

- `data` (list of float): The time series data.
- `periods` (int): The number of periods to forecast.

#### Returns

- `list of float`: The forecasted values for the next periods.

#### Example Usage

```python
from trend_analysis import forecast

data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
future_values = forecast(data, periods=3)
print(future_values)  # Output: [11, 12, 13]
```
