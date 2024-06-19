
# Theropoda Module

This module includes functionalities related to theropod dinosaurs.

## Overview

The `theropoda` module provides classes and functions to handle data and perform analyses related to theropod dinosaurs.

## Classes

### `Theropod`

Represents a theropod dinosaur.

#### Attributes

- `name` (str): The name of the theropod.
- `length` (float): The length of the theropod in meters.
- `weight` (float): The weight of the theropod in kilograms.
- `diet` (str): The diet type of the theropod (e.g., 'carnivore').

#### Methods

- `roar()`: Prints a roar from the theropod.

#### Example Usage

```python
from theropoda import Theropod

t_rex = Theropod(name="Tyrannosaurus Rex", length=12.3, weight=9000, diet="carnivore")
print(t_rex.name)  # Output: Tyrannosaurus Rex
t_rex.roar()  # Output: ROAR!!!
```

## Functions

### `find_largest_theropod(theropods)`

Finds the largest theropod in a list.

#### Parameters

- `theropods` (list of Theropod): A list of `Theropod` objects.

#### Returns

- `Theropod`: The largest theropod in the list.

#### Example Usage

```python
from theropoda import Theropod, find_largest_theropod

t_rex = Theropod(name="Tyrannosaurus Rex", length=12.3, weight=9000, diet="carnivore")
velociraptor = Theropod(name="Velociraptor", length=2.0, weight=15, diet="carnivore")

largest = find_largest_theropod([t_rex, velociraptor])
print(largest.name)  # Output: Tyrannosaurus Rex
```
