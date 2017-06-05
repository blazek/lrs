from hashlib import md5

from .lrsfeature import LrsFeature
from .lrsqualityfields import LRS_QUALITY_FIELDS


class LrsQualityFeature(LrsFeature):
    def __init__(self):
        super(LrsQualityFeature, self).__init__(LRS_QUALITY_FIELDS)
        self.checksum_ = None

    # full checksum, cannot be used to update existing feature because contains
    # geometry + all attributes
    def getChecksum(self):
        if not self.checksum_:
            #m = md5("%s" % self.geometry().exportToWkb())
            m = md5(self.geometry().exportToWkb())

            for attribute in self.attributes():
                m.update(str(attribute).encode())

            self.checksum_ = m.digest()
        return self.checksum_


