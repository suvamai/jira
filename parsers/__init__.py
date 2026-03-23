"""
Parser registry — maps broker keys to parser instances.
"""

from parsers.data_axle import DataAxleParser
from parsers.simiocloud import SimioCloudParser
from parsers.rmi_direct import RmiDirectParser
from parsers.celco import CelcoParser
from parsers.rkd_group import RkdGroupParser
from parsers.amlc import AmlcParser
from parsers.kap import KapParser
from parsers.washington_lists import WashingtonListsParser
from parsers.conrad_direct import ConradDirectParser
from parsers.names_in_news import NamesInNewsParser

PARSER_REGISTRY = {
    "data_axle":        DataAxleParser(),
    "simiocloud":       SimioCloudParser(),   # same format as data_axle
    "rmi_direct":       RmiDirectParser(),
    "celco":            CelcoParser(),
    "rkd_group":        RkdGroupParser(),
    "amlc":             AmlcParser(),
    "kap":              KapParser(),
    "washington_lists":  WashingtonListsParser(),
    "conrad_direct":    ConradDirectParser(),
    "names_in_news":    NamesInNewsParser(),
}
