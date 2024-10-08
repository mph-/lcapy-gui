from os.path import basename
from warnings import warn
from copy import copy

from lcapygui.ui.cross_hair import CrossHair
from lcapygui.ui.tk.menu_popup import MenuPopup, MenuDropdown
from lcapygui.ui.uimodelbase import Thing
from numpy import sqrt

from lcapy import Circuit
from lcapy.mnacpts import Cpt
from lcapy.nodes import Node
from .cursor import Cursor
from .cursors import Cursors
from .highlight import Highlight
from ..core.picture import Picture
from .action import ActionAdd, ActionDelete, ActionMove
from .uimodelbase import UIModelBase


class DragInfo:

    def __init__(self, cpts, nodes, positions):

        self.cpts = cpts
        self.nodes = nodes
        self.positions = positions

    @property
    def nodenames(self):

        return [node.name for node in self.nodes]

    @classmethod
    def from_cpts(cls, cpts):

        if not isinstance(cpts, list):
            cpts = [cpts]

        nodes = []
        positions = []
        for cpt in cpts:
            for node in cpt.nodes:
                if node.name not in nodes:
                    nodes.append(node)
                    positions.append((node.pos.x, node.pos.y))
        return cls(cpts, nodes, positions)

    @classmethod
    def from_nodes(cls, nodes):

        if not isinstance(nodes, list):
            nodes = [nodes]

        cpts = []
        for node in nodes:
            for cpt in node.connected:
                if cpt not in cpts:
                    cpts.append(cpt)

        positions = [(node.pos.x, node.pos.y) for node in nodes]
        return cls(cpts, nodes, positions)

    @classmethod
    def from_thing(cls, thing):

        if isinstance(thing, Node):
            return cls.from_nodes(thing)
        return cls.from_cpts(thing)


class UIModelDnD(UIModelBase):
    def __init__(self, ui):
        """
        Defines the UIModelDnD class

        Parameters
        ----------
        ui : lcapygui.ui.tk.lcapytk.LcapyTk
            tkinter UI interface

        Attributes
        ----------
        crosshair : CrossHair
            A crosshair for placing and moving components
        new_cpt : lcapygui.mnacpts.cpt or None
            The component currently being placed by the CrossHair
        node_positions : list of tuples or None
            Used for history, stores the node positions of the component or node before being moved
        """
        super(UIModelDnD, self).__init__(ui)

        self.last_pos = None
        self.cursors = Cursors()
        self.node_cursor = None

        self.key_bindings = {
            'ctrl+c': self.on_copy,
            'ctrl+d': self.on_debug,
            'ctrl+e': self.on_export,
            'ctrl+h': self.on_help,
            'ctrl+i': self.on_inspect,
            'ctrl+n': self.on_new,
            'ctrl+o': self.on_load,
            'ctrl+r': self.on_redraw,
            'ctrl+s': self.on_save,
            'alt+s': self.on_save_as,
            'ctrl+t': self.on_exchange_cursors,
            'ctrl+u': self.on_view,
            'ctrl+v': self.on_paste,
            'ctrl+w': self.on_quit,
            'ctrl+x': self.on_cut,
            'ctrl+y': self.on_redo,
            'ctrl+z': self.on_undo,
            'ctrl+9': self.on_pdb,
            'escape': self.on_unselect,
            'delete': self.on_delete,
            'backspace': self.on_delete}

        # Handle menu accelerator keys
        self.key_bindings_with_key = {}
        for k, thing in self.component_map.items():
            self.key_bindings_with_key[thing.accelerator] = self.on_add_cpt, thing
        for k, thing in self.connection_map.items():
            self.key_bindings_with_key[thing.accelerator] = self.on_add_con, thing

        if self.first_use:
            self.on_first_launch()
            self.preferences.save()

        self.crosshair = CrossHair(self)
        self.new_cpt = None
        self.node_positions = None
        self.highlight = Highlight(ui)

    def add_cursor(self, mouse_x, mouse_y):
        """
        Adds a cursor at the specified position on screen

        Parameters
        ----------
        mouse_x : float
            x position of the mouse on screen
        mouse_y : float
            y position of the mouse on screen

        Notes
        -----

        If there are no cursors, it will add a positive cursor
        If there is one cursor, it will add a negative cursor
        If there are two cursors, it will remove the first cursor, make the second positive, and add a new negative cursor
        """

        # Create a new temporary cursor
        cursor = Cursor(self.ui, mouse_x, mouse_y)

        if len(self.cursors) == 0:  # If no cursors, add positive one
            cursor.draw('positive')
            self.cursors.append(cursor)
            if self.ui.debug:
                print('Adding positive cursor')
        elif len(self.cursors) == 1:  # If one cursor, add negative one
            cursor.draw('negative')
            self.cursors.append(cursor)
            if self.ui.debug:
                print('Adding negative cursor')
        elif len(self.cursors) >= 2:  # If too many cursors, remove one and add
            self.cursors.pop(0)
            self.cursors.append(cursor)
            if self.ui.debug:
                print('Too many cursors, clearing all')

        # Refresh UI
        self.ui.refresh()
        return True if len(self.cursors) == 2 else False

    def snap_align_cursor(self, x, y):

        if len(self.cursors) < 1:
            return x, y, False

        xc = self.cursors[-1].x
        yc = self.cursors[-1].y

        if self.is_close_to(x, xc):
            if self.preferences.snap_grid:
                y = self.snap_to_grid_y(y)
            return xc, y, True

        if self.is_close_to(y, yc):
            if self.preferences.snap_grid:
                x = self.snap_to_grid_x(x)
            return x, yc, True

        return x, y, False

    def snap_to_cursor(self, x, y):

        for cursor in self.cursors:
            xc = cursor.x
            yc = cursor.y
            if self.is_close_to(x, xc) and self.is_close_to(y, yc):
                return xc, yc, True
        return x, y, False

    def snap_to_pin(self, x, y):

        cpt, pin = self.closest_pin(x, y)
        if pin:
            return pin.x, pin.y, True

        return x, y, False

    def snap(self, mouse_x, mouse_y, snap_to_component=False):
        """
        Snaps the x and y positions to the grid or to a component

        Parameters
        ----------
        mouse_x : float
            x position of the mouse on screen
        mouse_y : float
            y position of the mouse on screen
        snap_to_component : bool
            Determines if coords will snap to a selected component

        Returns
        -------
        tuple[float, float]
            The snapped x, y position
        """

        if snap_to_component:
            x, y, snapped = self.snap_to_pin(mouse_x, mouse_y)
            if snapped:
                return x, y

        x, y, snapped = self.snap_to_cursor(mouse_x, mouse_y)
        if snapped:
            return x, y

        x, y, snapped = self.snap_align_cursor(mouse_x, mouse_y)
        if snapped:
            return x, y

        if self.preferences.snap_grid:
            return self.snap_to_grid(mouse_x, mouse_y)

        # TODO: Try to align with pin or cursor...

        return mouse_x, mouse_y

    def clear(self):

        # TODO: better to remove the drawn artists
        # If don't want grid, use grid(False)

        # This removes the callbacks
        self.ui.clear(self.preferences.grid)

        ax = self.ui.canvas.drawing.ax
        ax.callbacks.connect('xlim_changed', self.on_mouse_zoom)
        ax.callbacks.connect('ylim_changed', self.on_mouse_zoom)

    def closest_cpt(self, x, y):
        """
        Returns the component closest to the specified position

        Parameters
        ==========
        x : float
            x position
        y : float
            y position

        Returns
        =======
        cpt: lcapy.mnacpts.Cpt or None
            the closest component to (x,y) or None if no component is close
        """
        for cpt in self.circuit.elements.values():
            gcpt = cpt.gcpt
            if gcpt is None:
                continue

            if gcpt.is_within_bbox(x, y):
                return cpt

        return None

    def component_between_cursors(self):
        """
        Returns the component between the two cursors, if present

        Returns
        -------
        lcapygui.mnacpts.cpt or None
            The component between the two cursors, if present

        """
        if len(self.cursors) < 2:
            return None

        x1 = self.cursors[0].x
        y1 = self.cursors[0].y
        x2 = self.cursors[1].x
        y2 = self.cursors[1].y

        for cpt in self.circuit.elements.values():
            if cpt is self:
                continue
            gcpt = cpt.gcpt
            if (gcpt.distance_from_cpt(x1, y1) < 0.2
                and gcpt.distance_from_cpt(x2, y2) < 0.2):
                return cpt
        return None

    def create_component_between_cursors(self, thing=None):
        """
        Creates a component between the two cursors, if present

        Parameters
        ----------
        thing : Thing, optional
            Used to decide an arbitrary component type if provided,
                otherwise will default to the self.crosshair.thing if available

        Returns
        -------
        bool
            Returns True if a component could have been created
            - There are 2 cursors to create a component between
            - A thing was provided, or available from self.crosshair.thing

        Notes
        -----
        This method will still return True, even if the component creation was unsuccessful. It only checks if it is
            provided enough information to create a component to pass into the :func:`self.create` method.

        """
        if len(self.cursors) < 2:
            if self.ui.debug:
                print('Not enough cursors to create component')
            return False

        x1 = self.cursors[0].x
        y1 = self.cursors[0].y
        x2 = self.cursors[1].x
        y2 = self.cursors[1].y

        if thing is None:
            if self.crosshair.thing is None:
                if self.ui.debug:
                    print('No thing provided to decide component type')
                return False
            thing = self.crosshair.thing

        self.cpt_create(thing.cpt_type, x1, y1, x2, y2, kind=thing.kind)

        self.ui.refresh()
        return True

    def create_state_space(self, cpt):
        """
        TODO: Correct Docstring

        Parameters
        ==========
        cpt : lcapy.mnacpts.Cpt
            Component to create state space for

        """
        ss = self.circuit.ss
        self.ui.show_state_space_dialog(ss)

    def create_transfer_function(self, cpt):
        """
        Shows the transfer function for the component 'cpt'

        Parameters
        ==========
        cpt : lcapy.mnacpts.Cpt
            Component to create transfer function for

        """
        self.ui.show_transfer_function_dialog(cpt)

    def create_twoport(self, cpt, kind):
        """
        TODO: add docstring

        Parameters
        ==========
        cpt : lcapy.mnacpts.Cpt
            Component to create twoport for
        kind : str
            String key for the twoport type

        """
        self.ui.show_twoport_dialog(cpt, kind)

    def exception(self, e):
        """
        Shows an error dialog with exception message 'e'

        Parameters
        ==========
        e : Exception

        """
        message = str(e)
        if self.pathname != '':
            message += ' in ' + self.pathname
        if self.ui.debug:
            breakpoint()
        self.ui.show_error_dialog(message)

    def exchange_cursors(self):

        if len(self.cursors) < 2:
            return
        self.cursors[0], self.cursors[1] = self.cursors[1], self.cursors[0]
        self.cursors[0].remove()
        self.cursors[1].remove()
        self.cursors[0].draw('positive')
        self.cursors[1].draw('negative')
        self.ui.refresh()

    def get_navigate_mode(self):
        """
        Returns the current navigate mode of the canvas

        e.g. ZOOM, PAN, etc.
        """
        return self.ui.canvas.drawing.ax.get_navigate_mode()

    def is_popup_active(self):
        """
        Returns True if a popup menu is currently active
        """
        return self.ui.popup_menu is not None

    def make_popup(self, menu_items):
        """
        Creates a popup menu

        Parameters
        ----------
        menu_items : list
            List of menu items to display in the popup

        """
        display_items = []
        for menu_item in menu_items:
            if menu_item[0] == '!':
                new_item = self.ui.menu_parts[menu_item[1:]]
                new_item.state = 'disabled'
            else:
                new_item = self.ui.menu_parts[menu_item]
                new_item.state = 'normal'
            display_items.append(new_item)

        self.ui.popup_menu = MenuPopup(self.ui,
                                       MenuDropdown('Right click',
                                                    0, display_items))


        self.ui.popup_menu.make(self.ui.level)
        self.ui.popup_menu.do_popup(self.ui.canvas.winfo_pointerx(),
                                    self.ui.canvas.winfo_pointery())

    def new_name(self, pathname):
        """
        This creates a modified version of the current pathname
        for use when a circuit is clones.

        Parameters
        ==========
        pathname : str
            Pathname of the file to create

        Returns
        =======
        str
            New pathname
        """
        from os.path import splitext

        base, ext = splitext(pathname)
        parts = base.split('_')
        if len(parts) == 0:
            suffix = '1'
        else:
            try:
                suffix = str(int(parts[-1]) + 1)
                base = '_'.join(parts[0:-1])
            except ValueError:
                suffix = '1'
        return base + '_' + suffix + ext

    def on_ac_model(self):
        """
        Changes the circuit to an AC model

        """
        # Perhaps should kill non-AC sources
        cct = self.circuit.ac()
        self.on_show_new_circuit(cct)

    def on_add_node(self, x, y):

        x, y = self.snap(x, y)

        self.add_cursor(x, y)

    def on_add_cpt(self, thing):
        """
        Configures crosshair and cursors for component creation.

        Parameters
        ----------
        thing
            The type of component to create

        Notes
        -----
        If there are two cursors, and there is no existing component between the cursoors , it will create a component between the cursors.

        Otherwise, it will initialise the crosshair to place a component of the given 'thing' type.

        """

        if len(self.cursors) >= 2:
            if self.component_between_cursors():
                warn('Placing component across another')

            self.create_component_between_cursors(thing)
        else:
            # Intialise crosshair to place a component of the given 'thing' type
            self.cursors.remove()
            if self.ui.debug:
                print(f'Crosshair mode: {self.crosshair.thing}')
            self.crosshair.update(thing=thing)

    def on_add_con(self, thing):
        """
        Configures crosshair and cursors for connection creation.

        Parameters
        ----------
        thing
            The connection to create

        Notes
        -----
        This method calls :func:`on_add_cpt` to configure the crosshair and cursors for connection creation.

        """
        # Set crosshair mode to the connection type
        self.on_add_cpt(thing)

    def on_best_fit(self):

        bbox = self.bounding_box()
        if bbox is None:
            return
        xmin, ymin, xmax, ymax = bbox

        self.ui.set_view(xmin - 2, ymin - 2, xmax + 2, ymax + 2)
        self.ui.refresh()

    def on_centre_fit(self):

        bbox = self.bounding_box()
        if bbox is None:
            return
        xmin, ymin, xmax, ymax = bbox

        xc = (xmin + xmax) / 2
        yc = (ymin + ymax) / 2
        xmin = xc - self.preferences.xsize / 2
        xmax = xc + self.preferences.xsize / 2
        ymin = yc - self.preferences.ysize / 2
        ymax = yc + self.preferences.ysize / 2

        self.ui.set_view(xmin, ymin, xmax, ymax)
        self.ui.refresh()

    def on_clone(self):

        pathname = self.new_name(self.pathname)
        self.save(pathname)

        model = self.ui.new()
        model.load(pathname)
        filename = basename(pathname)
        self.ui.set_filename(filename)
        self.ui.refresh()

    def on_close(self):
        """
        Close the lcapy-gui window

        """
        self.unmake_popup()
        self.ui.quit()

    def on_copy(self):
        """
        Copy the selected component

        """
        if self.selected is None:
            return
        if not self.cpt_selected:
            return

        self.copy(self.selected)

    def on_cpt_changed(self, cpt_or_node):

        self.invalidate()
        # Component name may have changed
        self.clear()

        if isinstance(cpt_or_node, Cpt):

            # If kind has changed need to remake the sketch
            # and remake the cpt.
            # If name changed need to remake the cpt.
            self.cpt_remake(cpt_or_node)
        elif isinstance(cpt_or_node, Node):
            # Node name may have changed...
            pass
        else:
            pass

        self.redraw()
        self.cursors.draw()
        self.ui.refresh()

    def on_create_state_space(self):

        self.create_state_space(self.selected)

    def on_create_transfer_function(self):

        self.create_transfer_function(self.selected)

    def on_create_twoport(self, kind):

        self.create_twoport(self.selected, kind)

    def on_cut(self):
        """
        If a component is selected, add it to the clipboard and remove it from the circuit

        """
        if not self.cpt_selected:
            return
        self.cut(self.selected)
        self.ui.refresh()

    def on_dc_model(self):

        # Perhaps should kill non-DC sources
        cct = self.circuit.dc()
        self.on_show_new_circuit(cct)

    def on_debug(self):

        s = ''
        s += 'Netlist.........\n'
        s += self.schematic() + '\n'
        s += 'Nodes...........\n'
        s += self.circuit.nodes.debug() + '\n'
        s += 'Cursors.........\n'
        s += self.cursors.debug() + '\n'
        s += 'Selected.........\n'
        s += str(self.selected) + '\n'
        s += '\nUndo_Buffer.........\n'
        s += str(self.undo_buffer) + '\n'
        s += '\nRedo_Buffer.........\n'
        s += str(self.redo_buffer) + '\n'
        s += '\nHistory.........\n'
        s += str(self.history)
        self.ui.show_message_dialog(s, 'Debug')

    def on_delete(self):
        """
        If a component is selected, delete it, then redraw and refresh the UI

        """
        if not self.cpt_selected:
            # Handle node deletion later
            return

        self.delete(self.selected)
        self.on_redraw()
        self.ui.refresh()

    def on_describe(self):

        self.ui.show_message_dialog(self.circuit.description(),
                                    title='Description')

    def on_exchange_cursors(self):

        self.exchange_cursors()

    def on_expand(self):

        cct = self.circuit.expand()
        self.on_show_new_circuit(cct)

    def on_export(self):

        pathname = self.ui.export_file_dialog(self.pathname)
        if pathname == '':
            return
        self.export(pathname)

    def on_expression(self):

        from lcapy import expr

        e = self.last_expr if self.last_expr is not None else expr(0)
        self.ui.show_expr_dialog(e)

    def on_help(self):

        self.ui.show_help_dialog()

    def on_inspect(self):

        if not self.selected:
            return

        if not self.cpt_selected:
            return

        self.ui.show_inspect_dialog(self.selected,
                                    title=self.selected.name)

    def on_inspect_properties(self):
        if self.cpt_selected:
            self.ui.inspect_properties_dialog(self.selected,
                                              self.on_cpt_changed,
                                              title=self.selected.name)
        else:
            self.ui.show_node_properties_dialog(self.selected,
                                                self.on_cpt_changed,
                                                title='Node ' +
                                                      self.selected.name)

    def on_inspect_current(self):

        if not self.selected or not self.cpt_selected:
            return

        cpt = self.selected
        win = self.ui.show_working_dialog('Calculating voltage')
        self.inspect_current(cpt)
        win.destroy()

    def on_inspect_noise_current(self):

        if not self.selected or not self.cpt_selected:
            return

        win = self.ui.show_working_dialog('Calculating noise current')
        self.inspect_noise_current(self.selected)
        win.destroy()

    def on_inspect_noise_voltage(self):

        if not self.selected or not self.cpt_selected:
            return

        win = self.ui.show_working_dialog('Calculating noise voltage')
        self.inspect_noise_voltage(self.selected)
        win.destroy()

    def on_inspect_norton_admittance(self):

        if not self.selected or not self.cpt_selected:
            return

        cpt = self.selected
        self.inspect_norton_admittance(cpt)

    def on_inspect_thevenin_impedance(self):

        if not self.selected or not self.cpt_selected:
            return

        cpt = self.selected
        self.inspect_thevenin_impedance(cpt)

    def on_inspect_voltage(self):

        if self.node_selected:
            node = self.selected
            win = self.ui.show_working_dialog('Calculating node voltage')
            self.inspect_node_voltage(node)
            win.destroy()

        elif self.cpt_selected:
            cpt = self.selected
            win = self.ui.show_working_dialog('Calculating voltage')
            self.inspect_voltage(cpt)
            win.destroy()

    def on_laplace_model(self):

        cct = self.circuit.s_model()
        self.on_show_new_circuit(cct)

    def on_left_click(self, mouse_x, mouse_y):
        """
        Performs operations on left click

        Parameters
        ----------
        mouse_x : float
            x position of the mouse on screen
        mouse_y : float
            y position of the mouse on screen

        Notes
        -----
        If not placing a component, it will attempt to select a component or node under the mouse.
        otherwise, if a component is being placed, the first node will be placed at the current position.


        """

        # Destroy all popups
        self.unmake_popup()

        # Select component/node under mouse
        self.on_select(mouse_x, mouse_y)

        # If a component is selected, do nothing
        if self.cpt_selected:
            self.cursors.remove()
            self.add_cursor(self.selected.gcpt.node1.pos.x,
                            self.selected.gcpt.node1.pos.y)
            node2 = self.selected.gcpt.node2
            if node2 is not None:
                self.add_cursor(node2.pos.x, node2.pos.y)
            if self.ui.debug:
                print('Selected component ' + self.selected.gcpt.name)
            return

        # If a node is selected, update mouse_x, mouse_y to that node's position
        if self.selected:
            if self.ui.debug:
                print('Selected node ' + self.selected.name)
            mouse_x, mouse_y = self.selected.pos.x, self.selected.pos.y
        else:  # Otherwise default to the crosshair position
            mouse_x, mouse_y = self.crosshair.position

        # Attempt to add a new cursor
        if ((not self.is_popup_active()) and
            self.add_cursor(mouse_x, mouse_y) and
                (len(self.cursors) == 2) and (self.crosshair.thing is not None)):
            self.create_component_between_cursors()
            self.crosshair.thing = None
            self.cursors.remove()

        self.on_redraw()

    def on_left_double_click(self, x, y):

        self.on_right_click(x, y)

    def on_load(self, initial_dir='.'):

        pathname = self.ui.open_file_dialog(initial_dir)
        if pathname == '' or pathname == ():
            return

        model = self.ui.new()
        model.load(pathname)
        self.ui.set_filename(pathname)
        self.ui.refresh()

    def on_manipulate_kill(self):

        # Could have a dialog to select what to kill

        cct = self.circuit.kill()
        self.on_show_new_circuit(cct)

    def on_manipulate_remove_sources(self):

        # Could have a dialog to select what to remove

        # Remove independent sources
        cct = self.circuit.copy()
        cct = cct.copy()
        values = list(cct.elements.values())
        for cpt in values:
            if cpt.is_independent_source:
                cct.remove(cpt.name)

        self.on_show_new_circuit(cct)

    def on_mesh_equations(self):

        try:
            la = self.circuit.loop_analysis()
        except Exception as e:
            self.exception(e)
            return

        eqns = la.mesh_equations()
        self.ui.show_equations_dialog(eqns, 'Mesh equations')

    def on_mouse_move(self, mouse_x, mouse_y):
        """
        Performs operations on mouse move

        Parameters
        ----------
        mouse_x : float
            x position of the mouse on screen
        mouse_y : float
            y position of the mouse on screen

        Notes
        -----
        Updates the crosshair position based on the mouse position.
        Will attempt to snap to the grid or to a component if the snap grid is enabled.

        """

        if False and self.get_navigate_mode() is not None:
            self.cursors.remove()
            self.crosshair.update(position=(mouse_x, mouse_y), style=None)
            return

        closest_cpt, closest_pin = self.closest_pin(mouse_x, mouse_y)

        if closest_pin is not None:
            # Update the crosshair position and set style to show it
            # is over a pin
            self.crosshair.update(position=(closest_pin.x,
                                            closest_pin.y), style='node')
            return

        closest_cpt = self.closest_cpt(mouse_x, mouse_y)
        if closest_cpt is not None:
            self.highlight.show(closest_cpt)
        else:
            self.highlight.remove()

        # If the crosshair is not over a node, snap to the grid (if
        # enabled)
        if self.preferences.snap_grid:

            dosnap = self.crosshair.thing is None
            mouse_x, mouse_y = self.snap(mouse_x, mouse_y,
                                         snap_to_component=dosnap)

        # Update position and reset style
        self.crosshair.update(position=(mouse_x, mouse_y), style=None)

    def cpt_drag(self, cpt, mouse_x, mouse_y, key):

        if not self.dragged:
            self.dragged = True

            x0, y0 = self.select_pos
            x0, y0 = self.snap(x0, y0)
            self.last_pos = x0, y0

            self.drag_info = DragInfo.from_cpts(cpt)

            if key == 'shift':
                # Separate component from connected nodes and add new nodes
                cpt = self.cpt_detach(cpt)
                self.select(cpt)

        x_0, y_0 = self.last_pos
        x_1, y_1 = self.snap(mouse_x, mouse_y, True)
        self.last_pos = x_1, y_1

        d_x = x_1 - x_0
        d_y = y_1 - y_0

        self.cpt_move(cpt, d_x, d_y, move_nodes=True)

    def node_attach1(self, node):

        nodes = self.overlapping_nodes(node.pos.x, node.pos.y, node)
        if len(nodes) == 0:
            return None

        if len(nodes) > 1:
            print('Non connected nodes', nodes)

        return nodes[0]

    def node_attach(self, node):

        anode = self.node_attach1(node)
        if anode is None:
            return

        if self.ui.debug:
            print('Renaming node', node.name, 'to', anode.name)

        self.node_rename(node, anode.name)

    def node_rename(self, node, new_name):

        if node.name == new_name:
            return

        node.rename(new_name)

        for cpt in node.connected:
            gcpt = cpt.gcpt
            for m, node1 in enumerate(gcpt.nodes):
                if node1.name == node.name:
                    gcpt.nodes[m] = node

    def node_drag(self, node, mouse_x, mouse_y, key):

        if not self.dragged:
            self.dragged = True
            self.drag_info = DragInfo.from_nodes(node)

        original_x, original_y = node.pos.x, node.pos.y

        node2 = self.closest_node(mouse_x, mouse_y)
        if node2:
            mouse_x, mouse_y = node2.pos.x, node2.pos.y

        else:
            # Check if aligned with a node on other end of component
            # to the specified node
            # node.connected_nodes in lcapy-1.22
            for cpt in node.connected:
                for node2 in cpt.nodes:
                    if node2 is node:
                        continue
                    x2, y2 = node2.x, node2.y
                    if self.is_close_to(mouse_x, x2):
                        mouse_x = x2
                    else:
                        mouse_x = self.snap_to_grid_x(mouse_x)
                    if self.is_close_to(mouse_y, y2):
                        mouse_y = y2
                    else:
                        mouse_y = self.snap_to_grid_y(mouse_y)

        self.node_move(node, mouse_x, mouse_y)

    def on_mouse_drag(self, mouse_x, mouse_y, key=None):
        """Performs operations when the user drags the mouse on the canvas.
        Everything here is run on every mouse movement, so should be
        kept as low cpu usage as possible.

        Explanation
        ------------
        If a chosen component is not created, it will create a new one at the current position
        If that component already exists, it will move the second node to the mouse position.

        It the chosen thing is a node, it will move that node to the current mouse position otherwise, it will attempt to drag a chosen component

        Parameters
        ----------
        mouse_x: float
            x position of the mouse
        mouse_y : float
            y position of the mouse
        key : str
            String representation of the pressed key.

        Notes
        -----
        If we are *dragging* to create a new component:
            If we have already created the component, and placed the first node:
                move the second node to the mouse position
            Otherwise, assume we haven't created the component yet, and create it at the current position
                (Initial creation size affects component scaling, so a large size is chosen to avoid scaling issues)

        Otherwise, assume we are dragging a component or a node.
            If a component is selected, move all its nodes to the new position, and store this position in history.  If 'shift' is pressed, detach the component from connected nodes
            If a node is selected, move that node to the new position, and store this position in history
        """

        # Disallow component placement and movement if in zoom mode.
        # Note, you can zoom in but then need to disable zoom mode.
        if self.get_navigate_mode() is not None:
            return

        if self.new_cpt is not None:
            # Placing second node of component

            gcpt = self.new_cpt.gcpt

            # Get crosshair position
            mouse_x, mouse_y = self.crosshair.position

            self.node_move(gcpt.node2, mouse_x, mouse_y)
            self.new_cpt.nodes[1].pos = gcpt.node2.pos
            return

        thing = self.crosshair.thing
        if thing is not None:
            # Placing first node of component

            if self.ui.debug:
                print('Creating new: ' + thing.kind)

            kind = '-' + thing.kind if thing.kind != '' else ''

            # Get crosshair position
            mouse_x, mouse_y = self.crosshair.position

            # Create a new component (the second node is filled in later)
            self.new_cpt = self.thing_create(
                thing.cpt_type,
                mouse_x,
                mouse_y,
                mouse_x + 2,
                # Have to be set to something larger because
                # components now scale to the initial size of the
                # component.
                mouse_y,
                kind=kind)

            # Clear cursors, as we don't need them when placing a component
            self.cursors.remove()
            return

        if not self.selected:
            return

        self.cursors.remove()

        if self.cpt_selected:
            self.cpt_drag(self.selected, mouse_x, mouse_y, key)
        else:
            self.node_drag(self.selected, mouse_x, mouse_y, key)

    def on_mouse_scroll(self, scroll_direction, mouse_x, mouse_y):
        """
        Performs operations on mouse scroll

        Parameters
        ----------
        scroll_direction : str
            String representation of the scroll direction
        mouse_x: float
            x position of the mouse
        mouse_y : float
            y position of the mouse

        Notes
        -----
        Rotates the selected component based on scroll direction. Currently only supports on 90 degree increments.
        """
        if self.selected and self.cpt_selected:
            # Rotate the component
            angle = 90 if scroll_direction == 'up' else -90
            self.rotate(self.selected, angle)
            self.selected.gcpt.undraw()
            self.selected.gcpt.draw(self)

    def on_mouse_release(self, key=None):
        """
        Performs operations on mouse release.

        High cpu usage operations should be placed here rather than in on_mouse_drag or on_mouse_move where possible, as this method is only called once per mouse release.

        Parameters
        ----------
        key : str or None
            String representation of the pressed key.

        Notes
        -----

        If placing a component with the mouse, we stop placing it, and add it to history.

        Otherwise, if a component is selected and has been moved, it will add the moved component to history.

        If a node is selected and has been moved, it will add the moved node to history.

        The screen is then completely redrawn to ensure accurate display of labels.
        """

        if self.ui.debug:
            print(f'left mouse release: key: {key}')

        if self.get_navigate_mode() is not None:
            return

        # If finished placing a component, stop placing
        if self.new_cpt is not None:

            node = self.new_cpt.gcpt.node2
            self.node_attach(node)

            # Add the brand new component to history
            self.history.add('Add', self.new_cpt)
            self.undo_buffer.append(ActionAdd(self.new_cpt))

            # Reset crosshair mode
            self.crosshair.thing = None
            self.new_cpt = None

        # If something is selected, and it has been moved
        elif self.selected is not None and self.dragged:

            info1 = self.drag_info
            info2 = DragInfo.from_thing(self.selected)

            for node in info2.nodes:
                self.node_attach(node)

            to_nodes = list(zip(info2.nodenames, info2.positions))
            from_nodes = list(zip(info1.nodenames, info1.positions))

            self.history.add('Move', info1.cpts, from_nodes, to_nodes)
            self.undo_buffer.append(ActionMove(info1.cpts,
                                                     from_nodes, to_nodes))

        # Redraw screen for accurate display of labels
        self.on_redraw()
        self.dragged = False


    def on_mouse_zoom(self, ax):
        """This is called whenever xlim or ylim changes; usually
        in response to selecting area with the mouse to zoom."""

        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        r = sqrt((xlim[1] - xlim[0]) ** 2 + (ylim[1] - ylim[0]) ** 2)

        xsize = self.preferences.xsize
        ysize = self.preferences.ysize
        R = sqrt(xsize ** 2 + ysize ** 2)
        self.zoom_factor = R / r

        if self.ui.debug:
            print('zoom %s' % self.zoom_factor)

        self.clear()
        self.redraw()

        # Don't refresh; will keep the old axes size
        # self.ui.refresh()

    def on_simple_netlist(self):

        netlist = []
        lines = self.circuit.netlist().split('\n')
        for line in lines:
            parts = line.split(';')
            netlist.append(parts[0].strip())
        s = '\n'.join(netlist)
        self.ui.show_message_dialog(s, 'Netlist')

    def on_netlist(self):

        s = self.schematic()
        self.ui.show_message_dialog(s, 'Netlist')

    def on_modified_nodal_equations(self):

        cct = self.analysis_circuit
        cct = cct.laplace()
        eqns = cct.matrix_equations()
        # Perhaps have matrix equation dialog?
        self.ui.show_expr_dialog(eqns, 'Modified nodal equations')

    def on_nodal_equations(self):

        try:
            na = self.circuit.nodal_analysis(node_prefix='n')
        except Exception as e:
            self.exception(e)
            return

        eqns = na.nodal_equations()
        self.ui.show_equations_dialog(eqns, 'Nodal equations')

    def on_new(self):

        self.ui.new()

    def cpt_detach(self, cpt):

        gcpt = cpt.gcpt

        # If the component is already separated, return it
        if (len(gcpt.node1.connected) <= 1 and len(gcpt.node2.connected) <= 1):
            return cpt

        # Create new nodes and rename cpt nodes to the new ones

        all_nodes = list(self.circuit.nodes.keys())
        old_nodes = cpt.nodes
        for node in cpt.nodes:
            new_node_name = gcpt.choose_node_name(0, all_nodes)
            all_nodes.append(new_node_name)
            node.rename(new_node_name, cpt)
        new_cpt = cpt

        if self.ui.debug:
            print('Detaching', cpt, 'as', new_cpt)

        for old_node, new_node in zip(old_nodes, new_cpt.nodes):
            new_node.pos = copy(old_node.pos)

        # Update gcpt nodes
        gcpt.update(nodes=new_cpt.nodes)

        self.check_drawable_nodes()

        return new_cpt

    def on_noise_model(self):

        cct = self.circuit.noise_model()
        self.on_show_new_circuit(cct)

    def on_paste(self):
        """
        If the clipboard is not empty, create a new component from the clipboard and add it to the circuit

        """
        if self.clipboard is None:
            if self.ui.debug:
                print('Nothing to paste')
            return

        if self.ui.debug:
            print('Pasting ' + self.clipboard.name)

        # Generate new thing from clipboard
        paste_thing = Thing(None, None, self.clipboard.type, '')
        self.on_add_cpt(paste_thing)

        self.ui.refresh()

    def on_pdb(self):

        import pdb
        pdb.set_trace()

    def on_preferences(self):

        def update():
            self.on_redraw()
            # Handle current_sign_convention
            self.invalidate()
            self.preferences.apply()

        self.ui.show_preferences_dialog(update)

    def on_first_launch(self):
        self.ui.show_first_launch_dialog()

    def on_quit(self):

        if self.dirty:
            self.ui.show_info_dialog('Schematic not saved')
        else:
            self.ui.quit()

    def on_redo(self):

        self.redo()
        self.ui.refresh()

    def on_redraw(self):
        """
        Redraws all objects on the screen

        """
        self.clear()
        self.redraw()
        self.cursors.draw()
        self.ui.refresh()

    def on_resize(self):

        if self.ui.debug:
            print('resize')

        # TODO:  fix up canvas size when maximize the window

    def on_right_click(self, mouse_x, mouse_y):
        """
        Performs operations on right click

        Parameters
        ----------
        mouse_x : float
            x position of the mouse on screen
        mouse_y : float
            y position of the mouse on screen

        Notes
        -----
        If placing a component, it cancels the place operation and deletes the component if it exists.
        otherwise, it will attempt to show a popup-menu
        - Component popup menu if a component is selected
        - Paste popup menu if no component is selected
        - Node popup if a node is selected
            - If that node is unjoined, show a join option if above another node
            - If joined, show an unjoin option

        """
        if self.get_navigate_mode() is not None:
            return

        # Destroy any created component
        if self.new_cpt is not None:
            self.cpt_delete(self.new_cpt)
            self.new_cpt = None

        # Clear cursors
        self.cursors.remove()
        self.ui.refresh()

        # Show right a click menu if not placing a component and there
        # are no cursors
        if self.crosshair.thing is None:
            self.on_select(mouse_x, mouse_y)

            if self.selected and self.cpt_selected:
                # If a component is selected
                self.make_popup(self.selected.gcpt.menu_items)

            elif self.node_selected:
                # If a node is selected
                self.make_popup(['dropdown_node_inspect_menu',
                                 'inspect_properties'])
            else:
                # If all else fails, show the paste popup
                if self.clipboard is None:
                    self.make_popup(['!edit_paste'])
                else:
                    self.make_popup(['edit_paste'])

        # Clear current placed component
        self.crosshair.thing = None

    def on_right_double_click(self, x, y):
        pass

    def on_rotate(self, angle):

        self.rotate(angle)

    def on_save(self):

        pathname = self.pathname
        if pathname == '':
            return
        self.save(pathname)
        self.ui.save(pathname)

    def on_save_as(self):

        pathname = self.ui.save_file_dialog(self.pathname)
        if pathname == '' or pathname == ():
            return
        self.save(pathname)
        self.ui.save(pathname)

    def on_screenshot(self):

        pathname = self.ui.export_file_dialog(self.pathname,
                                              default_ext='.png')
        if pathname == '' or pathname == ():
            return
        self.ui.screenshot(pathname)

    def on_select(self, x, y):

        self.select_pos = x, y

        node = self.closest_node(x, y)
        cpt = None
        if node is None:
            cpt = self.closest_cpt(x, y)

        if cpt:
            self.select(cpt)
            # TODO: only redraw selected component
            # Redraw to highlight selected component
            self.on_redraw()
        elif node:
            self.select(node)
        else:
            self.select(None)

    def on_show_new_circuit(self, cct):

        model = self.ui.new()
        model.load_from_circuit(cct)

        pathname = self.new_name(self.pathname)
        filename = basename(pathname)
        self.ui.set_filename(filename)
        self.ui.refresh()

    def on_transient_model(self):

        # Perhaps should kill non-transient sources
        cct = self.circuit.transient()
        self.on_show_new_circuit(cct)

    def on_undo(self):

        self.undo()
        self.on_redraw()

    def on_unselect(self):

        self.unselect()

    def on_view(self):

        self.view()

    def on_view_macros(self):

        from lcapy.system import tmpfilename
        from os import remove

        schtex_filename = tmpfilename('.schtex')

        cct = Circuit(self.schematic())
        cct.draw(schtex_filename)

        with open(schtex_filename) as f:
            content = f.read()
        remove(schtex_filename)

        self.ui.show_message_dialog(content)

    def unmake_popup(self):
        """
        Destroys the popup menu
        """
        if self.ui.popup_menu is not None:
            self.ui.popup_menu.undo_popup()
            self.ui.popup_menu = None

    def unselect(self):

        self.selected = None
        self.crosshair.thing = None
        self.crosshair.undraw()
        self.cursors.remove()
        self.redraw()
        self.ui.refresh()
