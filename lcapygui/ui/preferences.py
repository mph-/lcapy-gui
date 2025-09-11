from pathlib import Path
import json
from warnings import warn

# Perhaps make a dict?


class Preferences:

    circuitikz_default_line_width = 0.4   # pt
    circuitikz_default_scale = 1.0
    circuitikz_default_cpt_size = 1.5
    circuitikz_default_font_size = 12

    # For compatible colours, see https://matplotlib.org/stable/gallery/color/named_colors.html
    # mpl stylesheets available here, https://matplotlib.org/stable/gallery/style_sheets/style_sheets_reference.html
    color_schemes = {
        'default': {
            'tk_theme': None,
            'line': "black",
            'label': "black",
            'positive': 'red',
            'negative': 'blue',
            'select': 'purple',
            'grid': 'lightblue',
            'background': 'white'
        },
        'pastel': {
            'tk_theme': None,
            'line': 'black',
            'label': 'mediumpurple',
            'positive': 'lightcoral',
            'negative': 'cornflowerblue',
            'select': 'mediumpurple',
            'grid': 'lightblue',
            'background': 'white'
        },
        'greyscale': {
            'tk_theme': None,
            'line': 'black',
            'label': 'black',
            'positive': 'silver',
            'negative': 'silver',
            'select': 'dimgrey',
            'grid': 'gainsboro',
            'background': 'white'
        },
        'pitch': {
            'tk_theme': None,
            'line': 'silver',
            'label': 'white',
            'positive': 'silver',
            'negative': 'silver',
            'select': 'darkgray',
            'grid': 'dimgray',
            'background': 'black'
        },

    }

    def __init__(self):

        self.version = 6
        self.label_nodes = 'none'
        self.draw_nodes = 'connections'
        self.label_style = 'name'
        self.style = 'american'
        self.voltage_dir = 'RP'
        self.grid = 'on'
        # Line width in pt.
        self.line_width = self.circuitikz_default_line_width
        self.scale = self.circuitikz_default_scale
        self.show_units = 'false'
        self.xsize = 16
        self.ysize = 10
        self.snap_grid = 'true'
        # This is the scaling used to set the matplotlib line width
        # from the circuitikz line width.
        self.line_width_scale = 1.01 * 2.5
        self.node_size = 0.07
        self.node_color = 'black'
        self.current_sign_convention = 'passive'
        self.font_size = self.circuitikz_default_font_size
        self.cpt_size = self.circuitikz_default_cpt_size
        # This is used as the reference for component attributes in
        # a .sch file.  For example, R 1 2; right.
        self.node_spacing = 2.0
        self.grid_spacing = 0.5

        self.color_scheme = "default"

    def apply(self):

        from lcapy.rcparams import rcParams
        rcParams['circuit.current_sign_convention'] = self.current_sign_convention

    @property
    def _dirname(self):

        return Path('~/.lcapy/').expanduser()

    @property
    def _filename(self):

        return self._dirname / 'preferences.json'


    def color(self, element):
        if element in self.color_schemes[self.color_scheme].keys():
            return self.color_schemes[self.color_scheme][element]
        return self.color_schemes["default"][element]

    def load(self):

        dirname = self._dirname
        if not self._filename.exists():
            return False

        s = self._filename.read_text()
        d = json.loads(s)

        version = d.pop('version')

        for k, v in d.items():
            setattr(self, k, v)

        if hasattr(self, 'lw'):
            delattr(self, 'lw')
            warn('lw ignored, it is superseded by line_width')

        if (hasattr(self, 'line_width')
                and not isinstance(self.line_width, float)):
            if self.line_width.endswith('pt'):
                self.line_width = float(self.line_width[:-2])

        if not hasattr(self, 'scale'):
            self.scale = self.circuitikz_default_scale

        if hasattr(self, 'label_cpts'):
            warn('label_cpts is superseded by label_style')
            self.label_style = self.label_cpts
            if self.label_style == 'name+value':
                self.label_style = 'name=value'
            delattr(self, 'label_cpts')

        # Update the preferences file if the version changed
        if version != self.version:
            self.save()

        return True

    def reset(self):

        self.__init__()

    def save(self):

        dirname = self._dirname
        if not dirname.exists():
            dirname.mkdir()
        s = json.dumps(self, default=lambda o: o.__dict__,
                       sort_keys=True, indent=4)

        self._filename.write_text(s)

    def schematic_preferences(self):

        opts = ('draw_nodes', 'label_nodes', 'style', 'voltage_dir')

        foo = []
        for opt in opts:
            foo.append(opt + '=' + getattr(self, opt))
        s = ', '.join(foo)

        if self.line_width != self.circuitikz_default_line_width:
            s += ', line width=' + str(self.line_width)
        if self.scale != self.circuitikz_default_scale:
            s += ', scale=%.2f' % self.scale
        if self.cpt_size != self.circuitikz_default_cpt_size:
            s += ', cpt_size=%.2f' % self.cpt_size

        label_style = self.label_style
        if label_style == 'name=value':
            label_style = 'aligned'

        s += ', label_style=' + label_style

        return s
