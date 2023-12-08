from lcapygui.ui.history_event import HistoryEvent
from lcapygui.ui.uimodelmph import UIModelMPH
from .cross_hair import CrossHair


class UIModelDnD(UIModelMPH):

    """
    UIModelDnD

    Attributes
    ==========
    chain_path : lcapy.mnacpts.Cpt or None
        The component to be placed after a key is pressed

    """

    def __init__(self, ui):
        super(UIModelDnD, self).__init__(ui)
        self.chain_path = []
        self.crosshair = CrossHair(0, 0, self)
        self.new_component = None

    def on_add_cpt(self, thing):
        self.crosshair.style = thing.cpt_type
        print(self.crosshair.style)
        self.crosshair.undraw()
        self.crosshair.draw()
        self.ui.refresh()

    def on_mouse_release(self):
        super().on_mouse_release()

        # IF finished placing a component, stop placing
        if self.new_component is not None:
            # If the component is too small, delete it
            if self.new_component.gcpt.node1 == self.new_component.gcpt.node2:
                self.cpt_delete(self.new_component)
            else:
                self.crosshair.style = "default"

            self.new_component = None

        self.on_redraw()

    def on_left_click(self, x, y):
        if self.crosshair.style is None:
            super().on_left_click(x, y)

    def on_left_double_click(self, x, y):
        self.on_select(x, y)
        if self.cpt_selected and self.selected.gcpt.type == "DW":
            self.history.append(HistoryEvent("D", self.selected))
            self.selected.gcpt.convert_to_wires(self)
        else:
            super().on_left_double_click(x, y)

    def on_right_click(self, x, y):
        self.crosshair.style = "default"
        if self.new_component is not None:
            self.cpt_delete(self.new_component)
            self.new_component = None

    def on_mouse_move(self, mouse_x, mouse_y):
        # Snap mouse to grid
        if self.preferences.snap_grid:
            mouse_x, mouse_y = self.snap_to_grid(mouse_x, mouse_y)

        self.crosshair.update((mouse_x, mouse_y))

    def on_mouse_drag(self, mouse_x, mouse_y, key):
        """
        Performs operations on mouse drag

        Explanation
        -----------
        This function is called when the user drags the mouse on the canvas.

        Parameters
        ----------
        mouse_x: float
            x position of the mouse
        mouse_y : float
            y position of the mouse
        key : str
            String representation of the pressed key.

        Returns
        -------

        """
        if self.preferences.snap_grid:
            mouse_x, mouse_y = self.snap_to_grid(mouse_x, mouse_y)

        if self.crosshair.style is not None:
            if self.new_component is None:
                self.new_component = self.thing_create(
                    self.crosshair.style, mouse_x, mouse_y, mouse_x+.1, mouse_y
                )
            else:
                self.new_component.gcpt.node2.pos.x = mouse_x
                self.new_component.gcpt.node2.pos.y = mouse_y
                self.new_component.gcpt.undraw()
                self.new_component.gcpt.draw(self)
                self.ui.refresh()

        elif self.selected and not self.cpt_selected:
            new_x, new_y = self.snap_to_grid(mouse_x, mouse_y)

            self.selected.pos.x = new_x
            self.selected.pos.y = new_y

            for cpt in self.selected.connected:
                cpt.gcpt.undraw()
                cpt.gcpt.draw(self)

                self.ui.refresh()
        # else:
        #     super().on_mouse_drag(mouse_x, mouse_y, key)
