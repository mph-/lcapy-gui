from ..annotation import Annotation
from ..annotations import Annotations
from .preferences import Preferences
from ..components.cpt_maker import cpt_make, cpt_remake

from copy import copy
from math import atan2, degrees, sqrt
from lcapy import Circuit, expr
from lcapy.mnacpts import Cpt, Eopamp
from lcapy.nodes import parse_nodes
from lcapy.schemmisc import Pos


class UIModelBase:

    STEP = 2
    SNAP = 1
    SCALE = 0.25

    # Short-cut key, name, type, kind
    component_map = {
        'c': ('c', 'Capacitor', 'C', ''),
        'd': ('d', 'Diode', 'D', ''),
        'i': ('i', 'Current source', 'I', ''),
        'j': ('j', 'JFET', 'J', ''),
        'l': ('l', 'Inductor', 'L', ''),
        'm': ('m', 'MOSFET', 'M', ''),
        'q': ('q', 'BJT', 'Q', ''),
        'r': ('r', 'Resistor', 'R', ''),
        'nr': ('', 'Noiseless resistor', 'R', ''),
        'v': ('v', 'Voltage source', 'V', ''),
        'w': ('w', 'Wire', 'W', ''),
        'e': ('e', 'VCVS', 'E', ''),
        'f': ('f', 'CCCS', 'F', ''),
        'g': ('g', 'VCCS', 'G', ''),
        'h': ('h', 'CCVS', 'H', ''),
        'opamp': ('', 'Opamp', 'Opamp', ''),
        'p': ('p', 'Port', 'P', ''),
        'y': ('y', 'Admittance', 'Y', ''),
        'z': ('z', 'Impedance', 'Z', ''),
        'cpe': ('', 'CPE', 'CPE', ''),
    }

    connection_map = {
        '0': ('0', '0V', 'Ground', ''),
        '0V': ('', '0V', 'Ground', '0V'),
        'ground': ('', 'Ground', 'Ground', ''),
        'sground': ('', 'Signal ground', 'Ground', 'sground'),
        'rground': ('', 'Rail ground', 'Ground', 'rground'),
        'cground': ('', 'Chassis ground', 'Ground', 'cground'),
        # 'vdd': ('VDD', 'A', 'vdd'),
        # 'vss': ('VSS', 'A', 'vss'),
        # 'input': ('Input', 'A', 'input'),
        # 'output': ('Output', 'A', 'output'),
        # 'bidir': ('Bidirectional', 'A', 'bidir')
    }

    def __init__(self, ui):

        self.circuit = Circuit()
        self.ui = ui
        self._analysis_circuit = None
        self.filename = ''
        self.voltage_annotations = Annotations()
        self.selected = None
        self.last_expr = None
        self.preferences = Preferences()
        self.dirty = False
        self.history = []
        self.clipboard = None

    @property
    def analysis_circuit(self):
        """This like circuit but it has an added ground node if one does
        not exist.

        """

        if self._analysis_circuit is not None:
            return self._analysis_circuit

        if self.circuit.elements == {}:
            self.exception('No circuit defined')
            return None

        self._analysis_circuit = self.circuit.copy()

        if self.ground_node is None:
            # Add dummy ground node to first node
            net = 'W %s 0\n' % list(self.circuit.nodes)[0]
            self.analysis_circuit.add(net)

        try:
            self._analysis_circuit[0]
        except (AttributeError, ValueError, RuntimeError) as e:
            self.exception(e)
            return None

        return self._analysis_circuit

    def bounding_box(self):

        if len(self.circuit.nodes) == 0:
            return None

        xmin = 1000
        xmax = 0
        ymin = 1000
        ymax = 0
        for node in self.circuit.nodes.values():
            if node.x < xmin:
                xmin = node.x
            if node.x > xmax:
                xmax = node.x
            if node.y < ymin:
                ymin = node.y
            if node.y > ymax:
                ymax = node.y
        return xmin, ymin, xmax, ymax

    def choose_cpt_name(self, cpt_type):

        num = 1
        while True:
            name = cpt_type + str(num)
            if name not in self.circuit.elements:
                return name
            num += 1

    def choose_node_name(self, nodes):

        num = 1
        while True:
            name = str(num)
            if name not in nodes:
                return name
            num += 1

    def con_create(self, con_key, x1, y1, x2, y2):
        """Create a new connection."""

        try:
            cpt_type = self.connection_map[con_key][2]
        except KeyError:
            return None

        if cpt_type == '':
            return None

        return self.thing_create(cpt_type, x1, y1, x2, y2)

    def copy(self, cpt):

        self.clipboard = cpt

    @property
    def cpt_selected(self):

        return isinstance(self.selected, Cpt)

    def cpt_create(self, cpt_key, x1, y1, x2, y2):
        """Create a new component."""

        s = sqrt((x1 - x2)**2 + (y1 - y2)**2)
        if s < 0.2:
            self.exception('Nodes too close to create component')
            return

        try:
            cpt_type = self.component_map[cpt_key][2]
        except KeyError:
            return None

        if cpt_type == '':
            return None

        return self.thing_create(cpt_type, x1, y1, x2, y2)

    def cpt_delete(self, cpt):

        self.select(None)

        redraw = True
        try:
            # This should also delete the annotations.
            cpt.undraw()
            redraw = False
        except AttributeError:
            pass

        self.circuit.remove(cpt.name)

        if redraw:
            self.ui.clear()
            self.redraw()

    def cpt_draw(self, cpt):

        gcpt = cpt.gcpt
        if gcpt is None:
            return

        gcpt.draw(self, self.ui.sketcher)

        label_cpts = self.preferences.label_cpts

        if gcpt.type in ('A', 'O', 'W'):
            label_cpts = 'none'

        name = cpt.name

        try:
            value = '$' + expr(cpt.args[0]).latex() + '$'
        except IndexError:
            value = None

        if value is None:
            value = ''

        if label_cpts == 'name+value':
            if name != value and gcpt.type != 'P':
                label = name + '=' + value
            else:
                label = name
        elif label_cpts == 'value':
            if value != '':
                label = value
            else:
                label = name
        elif label_cpts == 'name':
            label = name
        elif label_cpts == 'none':
            label = ''
        else:
            raise RuntimeError('Unhandled label_cpts=' + label_cpts)

        if label != '':
            ann = Annotation(self.ui, gcpt.label_position.x,
                             gcpt.label_position.y, label)
            ann.draw(fontsize=18)
            gcpt.annotations.append(ann)

        draw_nodes = self.preferences.draw_nodes
        if draw_nodes != 'none':
            for node in cpt.nodes:
                if node.port:
                    self.node_draw(node)
                    continue

                if draw_nodes == 'connections' and node.count < 3:
                    continue
                if draw_nodes == 'primary' and not node.is_primary:
                    continue
                self.node_draw(node)

        label_nodes = self.preferences.label_nodes
        if label_nodes != 'none':
            for node in cpt.nodes:
                if node.name[0] == '_':
                    continue

                if label_nodes == 'alpha' and not node.name[0].isalpha():
                    continue

                x, y = node.pos.x, node.pos.y
                # Should be x -= 0.1 but need to right justify.
                x += 0.1
                y += 0.1
                ann = Annotation(self.ui, x, y, node.name)
                ann.draw(fontsize=18)
                gcpt.annotations.append(ann)

    def cpt_find(self, node_name1, node_name2):

        fcpt = None
        for cpt in self.circuit:
            if (cpt.nodes[0].name == node_name1 and cpt.nodes[1].name == node_name2):
                fcpt = cpt
                break
        if fcpt is None:
            self.exception(
                'Cannot find a component with nodes %s and %s' % (node_name1, node_name2))
        return fcpt

    def cpt_remake(self, cpt):

        gcpt = cpt.gcpt

        if cpt.is_dependent_source:
            try:
                newcpt = cpt._change_control(gcpt.control)
            except Exception:
                self.exception('Control component %s for %s deleted' %
                               (gcpt.control, cpt.name))
                return
        elif gcpt.cpt_kind == cpt._kind:
            newcpt = cpt
        else:
            newcpt = cpt._change_kind(gcpt.cpt_kind)

        newcpt.gcpt = cpt.gcpt
        cpt_remake(newcpt.gcpt)

    def cut(self, cpt):

        self.delete(cpt)
        self.clipboard = cpt

    def delete(self, cpt):

        self.cpt_delete(cpt)
        self.history.append((cpt, 'D'))

    def draw(self, cpt, **kwargs):

        if cpt is None:
            return
        cpt.draw(**kwargs)

    def export(self, filename):

        cct = self.circuit
        cct.draw(filename)

    def invalidate(self):

        self._analysis_circuit = None

    def load(self, filename):

        from lcapy import Circuit

        self.filename = filename

        with open(filename) as f:
            line = f.readline()
            if line.startswith(r'\begin{tikz'):
                self.ui.show_error_dialog('Cannot load Circuitikz macro file')
                return

        try:
            circuit = Circuit(filename)
        except Exception as e:
            self.exception(e)
            return

        return self.load_from_circuit(circuit)

    def load_from_circuit(self, circuit):

        self.circuit = circuit
        positions = None
        for cpt in self.circuit.elements.values():
            if cpt.type == 'XX' and 'nodes' in cpt.opts:
                positions = parse_nodes(cpt.opts['nodes'])
                break

        if positions is not None:

            for k, v in self.circuit.nodes.items():
                v.pos = positions[k]

        else:

            # Node positions not defined.

            sch = self.circuit.sch

            try:
                # This will fail if have detached components.
                calculated = sch._positions_calculate()
            except (AttributeError, ValueError, RuntimeError) as e:
                self.exception(e)
                return

            width, height = sch.width * self.STEP, sch.height * self.STEP

            # Centre the schematic.
            xsize = self.ui.canvas.drawing.xsize
            ysize = self.ui.canvas.drawing.ysize
            offsetx, offsety = self.snap((xsize - width) / 2,
                                         (ysize - height) / 2)
            for node in sch.nodes.values():
                node.pos.x += offsetx
                node.pos.y += offsety
                circuit.nodes[node.name].pos = node.pos

        self.remove_directives()

        for cpt in self.circuit.elements.values():
            if cpt.type == 'XX':
                cpt.gcpt = None
                continue
            try:
                cpt_type = cpt.type
                if isinstance(cpt, Eopamp):
                    cpt_type = 'Opamp'
                gcpt = cpt_make(cpt_type, kind=cpt._kind)
                # FIXME.
                gcpt.name = cpt.name
                gcpt.nodes = cpt.nodes
            except Exception as e:
                cgpt = None
                self.exception(e)

            cpt.gcpt = gcpt

        self.invalidate()
        self.redraw()

    def move(self, xshift, yshift):
        # TODO
        pass

    def paste(self, x1, y1, x2, y2):

        if self.clipboard is None:
            return

        return self.thing_create(self.clipboard.type, x1, y1, x2, y2)

    def possible_control_names(self):

        cpts = self.circuit.elements.values()
        names = [c.name for c in cpts if c.name[0] != 'W']
        return names

    def remove_directives(self):

        elt_list = list(self.circuit.elements.values())
        if elt_list == []:
            return

        cpt = elt_list[-1]
        if cpt.type == 'XX':
            # TODO: make more robust
            # This tries to remove the schematic attributes.
            # Perhaps parse this and set preferences but this
            # might be confusing.
            self.circuit.remove(cpt.name)
            cpt = elt_list[0]

        if cpt.type == 'XX' and cpt._string.startswith('# Created by lcapy'):
            self.circuit.remove(cpt.name)

        if len(elt_list) > 1:
            cpt = elt_list[1]
            if cpt.type == 'XX' and cpt._string.startswith('; nodes='):
                self.circuit.remove(cpt.name)

    def rotate(self, angle):
        # TODO
        pass

    def save(self, filename):

        s = self.schematic()

        with open(filename, 'w') as fhandle:
            fhandle.write(s)
        self.dirty = False

    def schematic(self):

        s = '# Created by ' + self.ui.NAME + ' V' + self.ui.version + '\n'

        # Define node positions
        foo = [str(node) for node in self.circuit.nodes.values()]
        s += '; nodes={' + ', '.join(foo) + '}' + '\n'

        for cpt in self.circuit.elements.values():

            net_string = str(cpt)
            parts = net_string.split(';')
            net_string = parts[0]
            s += net_string
            if cpt.gcpt is not None:
                s += '; ' + cpt.gcpt.attr_string(self.STEP) + '\n'

        # FIXME, remove other preference string
        # Note, need a newline so string treated as a netlist string
        s += '; ' + self.preferences.schematic_preferences() + '\n'
        return s

    def thing_create(self, cpt_type, x1, y1, x2, y2):

        gcpt = cpt_make(cpt_type)

        cpt_name = self.choose_cpt_name(gcpt.type)
        gcpt.name = cpt_name

        nodes = list(self.circuit.nodes)
        positions = gcpt.assign_positions(x1, y1, x2, y2)

        parts = [cpt_name]
        for m, position in enumerate(positions):
            node = self.circuit.nodes.by_position(position)
            if node is None:
                node_name = self.choose_node_name(nodes)
                nodes.append(node_name)
            else:
                node_name = node.name
            parts.append(node_name)

        if cpt_type in ('E', 'G'):
            # Use cpt for its control.  This is temporary until the
            # user changes it.
            parts.extend([parts[1], parts[2]])
            gcpt.control = cpt_name
        elif cpt_type in ('F', 'H'):
            parts.append('X')

        netitem = ' '.join(parts)

        if self.ui.debug:
            print('Adding ' + netitem)

        cct = self.circuit.add(netitem)
        cpt = cct[cpt_name]

        for m, position in enumerate(positions):
            cpt.nodes[m].pos = Pos(position)

        # Duck type
        cpt.gcpt = gcpt
        gcpt.nodes = cpt.nodes

        self.cpt_draw(cpt)

        self.history.append((cpt, 'A'))

        return cpt

    def inspect_admittance(self, cpt):

        try:
            self.last_expr = self.analysis_circuit[cpt.name].Y
            self.ui.show_expr_dialog(self.last_expr,
                                     '%s admittance' % cpt.name)
        except (AttributeError, ValueError, RuntimeError) as e:
            self.exception(e)

    def inspect_current(self, cpt):

        # TODO: FIXME for wire current
        try:
            self.last_expr = self.analysis_circuit[cpt.name].i
            self.ui.show_expr_dialog(self.last_expr,
                                     '%s current' % cpt.name)
        except (AttributeError, ValueError, RuntimeError) as e:
            self.exception(e)

    def inspect_impedance(self, cpt):

        try:
            self.last_expr = self.analysis_circuit[cpt.name].Z
            self.ui.show_expr_dialog(self.last_expr,
                                     '%s impe' % cpt.name)
        except (AttributeError, ValueError, RuntimeError) as e:
            self.exception(e)

    def inspect_norton_admittance(self, cpt):

        try:
            self.last_expr = self.analysis_circuit[cpt.name].dpY
            self.ui.show_expr_dialog(self.last_expr,
                                     '%s Norton admittance' % cpt.name)
        except (AttributeError, ValueError, RuntimeError) as e:
            self.exception(e)

    def inspect_thevenin_impedance(self, cpt):

        try:
            self.last_expr = self.analysis_circuit[cpt.name].dpZ
            self.ui.show_expr_dialog(self.last_expr,
                                     '%s Thevenin impedance' % cpt.name)
        except (AttributeError, ValueError, RuntimeError) as e:
            self.exception(e)

    def inspect_voltage(self, cpt):

        try:
            self.last_expr = self.analysis_circuit[cpt.name].v
            self.ui.show_expr_dialog(self.last_expr,
                                     '%s potential difference' % cpt.name)
        except (AttributeError, ValueError, RuntimeError) as e:
            self.exception(e)

    def show_node_voltage(self, node):

        try:
            self.last_expr = self.analysis_circuit[node.name].v
            self.ui.show_expr_dialog(self.last_expr,
                                     'Node %s potential' % node.name)
        except (AttributeError, ValueError, RuntimeError) as e:
            self.exception(e)

    def select(self, thing):

        self.selected = thing

    def snap(self, x, y):

        snap = self.SNAP
        x = (x + 0.5 * snap) // snap * snap
        y = (y + 0.5 * snap) // snap * snap
        return x, y

    def unselect(self):
        pass

    def view(self):

        cct = Circuit(self.schematic())
        cct.draw()

    def voltage_annotate(self, cpt):

        ann1 = Annotation(self.ui, *cpt.nodes[0].pos, '+')
        ann2 = Annotation(self.ui, *cpt.nodes[1].pos, '-')

        self.voltage_annotations.add(ann1)
        self.voltage_annotations.add(ann2)
        ann1.draw(color='red', fontsize=40)
        ann2.draw(color='blue', fontsize=40)

    @property
    def ground_node(self):

        return self.node_find('0')

    def node_draw(self, node):

        if node.port:
            self.ui.sketcher.stroke_circle(
                node.x, node.y, self.preferences.node_size,
                color=self.preferences.node_color, alpha=1)
        else:
            self.ui.sketcher.stroke_filled_circle(
                node.x, node.y, self.preferences.node_size,
                color=self.preferences.node_color, alpha=1)

    def node_find(self, nodename):

        for node in self.circuit.nodes.values():
            if node.name == nodename:
                return node
        return None

    def redo(self):

        # TODO
        pass

    def redraw(self):

        for cpt in self.circuit.elements.values():
            self.cpt_draw(cpt)

    def undo(self):

        if self.history == []:
            return
        cpt, op = self.history.pop()
        if op == 'D':
            self.circuit.add(str(cpt))

            # Copy node positions
            new_cpt = self.circuit.elements[cpt.name]
            for m, node in enumerate(cpt.nodes):
                new_cpt.nodes[m].pos = node.pos
            new_cpt.gcpt = cpt.gcpt

            self.cpt_draw(cpt)
            self.select(cpt)
        else:
            self.cpt_delete(cpt)
        self.invalidate()
