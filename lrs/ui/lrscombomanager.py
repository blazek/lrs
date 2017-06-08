from .lrscombomanagerbase import LrsComboManagerBase


class LrsComboManager(LrsComboManagerBase):
    def __init__(self, comboOrList, **kwargs):
        super(LrsComboManager, self).__init__(comboOrList, **kwargs)
        self.connectCombos()