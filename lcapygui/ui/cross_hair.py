from lcapygui.components.picture import Picture
from typing import Tuple


class CrossHair:
    def __init__(self, x, y, model, style="cross", label=None):
        self.position = x, y
        self.model = model
        self.style = style
        self.label = None
        self.picture = None

    @property
    def position(self) -> Tuple[int, int]:
        return self.__x, self.__y

    @position.setter
    def position(self, coords: Tuple[int, int]):
        self.__x = coords[0]
        self.__y = coords[1]

    @property
    def style(self) -> str:
        return self.__style

    @style.setter
    def style(self, style: str):
        self.__style = style

    def draw(self):
        """
        Draws a crosshair at the specified coordinates

        Parameters
        ==========
        model : lcapygui.ui.uimodelbase.UIModelBase or lcapygui.ui.uimodelmph.UIModelMPH or lcapygui.ui.uimodeldnd.UIModelDnD
            UI Model to draw to

        """
        scale = self.model.preferences.xsize/20
        sketcher = self.model.ui.sketcher
        self.picture = Picture()
        # Nothing is selected
        if self.style == None:
            self.picture.add(
                sketcher.stroke_line(
                    self.__x, self.__y - 0.5 * scale, self.__x, self.__y + 0.5*scale, linewidth=1
                )
            )
            self.picture.add(
                sketcher.stroke_line(
                    self.__x - 0.5*scale, self.__y, self.__x + 0.5*scale, self.__y, linewidth=1
                )
            )
        # Drawing a Wire
        elif self.style == "W":
            self.picture.add(
                sketcher.stroke_filled_circle(
                    self.__x, self.__y, radius=0.2*scale, color="green", alpha=1
                )
            )
        # Drawing the component type to be placed
        else:
            self.picture.add(
                sketcher.stroke_line(
                    self.__x, self.__y - 0.5*scale, self.__x, self.__y + 0.5*scale, linewidth=1
                )
            )
            self.picture.add(
                sketcher.stroke_line(
                    self.__x - 0.5*scale, self.__y, self.__x + 0.5*scale, self.__y, linewidth=1
                )
            )

            self.picture.add(sketcher.text(self.__x+.1*scale, self.__y+.1*scale, self.style, fontsize=self.model.preferences.font_size * self.model.zoom_factor * self.model.preferences.line_width_scale))

    def undraw(self):
        """
        Undraws the crosshair

        """
        if self.picture is not None:
            self.picture.remove()

    def update(self, mouse_position, style=None, model=None):
        """
        Allows updating all parameters, and redrawing the crosshair in one function
        Parameters
        ==========
        mouse_position : Tuple[int, int]
            Position of the mouse
        style : str
            Style of the crosshair
        model : lcapygui.ui.uimodelbase.UIModelBase or lcapygui.ui.uimodelmph.UIModelMPH or lcapygui.ui.uimodeldnd.UIModelDnD
            UI Model to draw to

        """

        # Update parameters
        self.position = mouse_position

        if style is not None:
            self.style = style

        if model is not None:
            self.model = model

        # Redraw the component
        self.undraw()
        self.draw()
        self.model.ui.refresh()