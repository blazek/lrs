from .lrsroutebase import LrsRouteBase


# Route loaded from LRS layer
class LrsLayerRoute(LrsRouteBase):
    def __init__(self, routeId,**kwargs):
        super(LrsLayerRoute, self).__init__(routeId,**kwargs)
