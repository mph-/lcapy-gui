from .component import Component
from .picture import Picture
from .pos import Pos
from numpy import array, sqrt


class Stretchy(Component):

    can_stretch = True

    def draw(self, model, **kwargs):
        """
        Handles drawing specific features of components.
        """

        sketch = self._sketch_lookup(model)

        # Handle ports where nothing is drawn.
        if sketch is None or self.type == 'P':
            return

        kwargs = self.make_kwargs(model, **kwargs)

        if 'invisible' in kwargs or 'nodraw' in kwargs or 'ignore' in kwargs:
            return

        x1, y1 = self.node1.x, self.node1.y
        x2, y2 = self.node2.x, self.node2.y
        dx = x2 - x1
        dy = y2 - y1

        r = self.length
        if r == 0:
            model.ui.show_warning_dialog(
                'Ignoring zero size component ' + self.name)
            return

        # This scales the component size but not the distance between
        # the nodes (default 1)
        scale = float(self.scale)
        if scale > r:
            scale = r

        # Width in cm
        w = sketch.width_cm * scale

        p1 = Pos(x1, y1)
        p2 = Pos(x2, y2)

        if r != 0:
            dw = Pos(dx, dy) / r * (r - w) / 2
            p1p = p1 + dw
            p2p = p2 - dw
        else:
            # For zero length wires
            p1p = p1
            p2p = p2

        sketcher = model.ui.sketcher
        self.picture = Picture()

        tf = self.make_tf(p1p, p2p, self.pos1, self.pos2)

        self.picture.add(sketch.draw(model, tf, **kwargs))

        # TODO: generalize
        kwargs.pop('mirror', False)
        kwargs.pop('invert', False)

        self.picture.add(sketcher.stroke_line(*p1.xy, *p1p.xy, **kwargs))
        self.picture.add(sketcher.stroke_line(*p2p.xy, *p2.xy, **kwargs))

        # TODO, add label, voltage_label, current_label, flow_label