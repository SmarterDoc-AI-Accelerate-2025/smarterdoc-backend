########################################
# Only working with Tri-State Area in NY
########################################
from enum import Enum


class MetroSlug(str, Enum):
    NYC = "nyc"

    LONG_ISLAND = "long-island"

    NORTH_JERSEY = "north-jersey"

    CONNECTICUT_AREA = "ct"
