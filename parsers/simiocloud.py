"""Parser for SimioCloud broker PDF orders -- same format as Data Axle."""

from parsers.data_axle import DataAxleParser


class SimioCloudParser(DataAxleParser):
    broker_key: str = "simiocloud"
