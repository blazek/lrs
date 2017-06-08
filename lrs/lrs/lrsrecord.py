class LrsRecord:
    def __init__(self, milestoneFrom, milestoneTo, partFrom, partTo):
        # measures from milestone measure attribute
        self.milestoneFrom = milestoneFrom
        self.milestoneTo = milestoneTo
        # convert to float to don't care later about operations with integers
        # (it should come here already as float)
        # (it can also be used as milestoneFrom or milestoneTo = None)
        if self.milestoneFrom is not None:
            self.milestoneFrom = float(self.milestoneFrom)
        if self.milestoneTo is not None:
            self.milestoneTo = float(self.milestoneTo)

        # measures measured along part polyline
        self.partFrom = partFrom
        self.partTo = partTo
        # debug( "LrsRecord.init() milestoneFrom = %s milestoneTo = %s partFrom = %s partTo = %s" % ( milestoneFrom, milestoneTo, partFrom, partTo) )

    def __str__(self):
        return "record %s-%s / %s-%s" % (self.milestoneFrom, self.milestoneTo, self.partFrom, self.partTo)

    # returns true if measure is within open interval (milestoneFrom,milestoneTo)
    # i.e. milestoneFrom < measure < milestoneTo
    def measureWithin(self, measure):
        return self.milestoneFrom < measure < self.milestoneTo

    def containsMeasure(self, measure):
        return self.milestoneFrom <= measure <= self.milestoneTo

    def partMeasureWithin(self, measure):
        return self.partFrom < measure < self.partTo

    def containsPartMeasure(self, measure):
        return self.partFrom <= measure <= self.partTo

    # returns true if measure at least partially overlaps with another record
    def measureOverlaps(self, record):
        if self.measureWithin(record.milestoneFrom):
            return True
        if self.measureWithin(record.milestoneTo):
            return True
        if record.measureWithin(self.milestoneFrom):
            return True
        if record.measureWithin(self.milestoneTo):
            return True
        if record.measureWithin((self.milestoneFrom + self.milestoneTo) / 2):
            return True
        return False

    # get measure for part measure
    def measure(self, partMeasure):
        md = self.milestoneTo - self.milestoneFrom
        pd = self.partTo - self.partFrom
        k = (partMeasure - self.partFrom) / pd
        return self.milestoneFrom + k * md

    # get distance from part beginning
    def partMeasure(self, measure):
        md = self.milestoneTo - self.milestoneFrom
        pd = self.partTo - self.partFrom
        k = (measure - self.milestoneFrom) / md
        return self.partFrom + k * pd

    # True if nextRecord continues measure without gap in both milestone
    # and part measures
    def continues(self, nextRecord):
        return nextRecord.milestoneFrom == self.milestoneTo and nextRecord.partFrom == self.partTo

    def milestonesDistance(self):
        return abs(self.milestoneTo-self.milestoneFrom)