from tkinter import Toplevel, Button
from .labelentries import LabelEntry, LabelEntries
from .menu import MenuDropdown, MenuItem
from .window import Window


class CptPropertiesDialog(Window):

    def __init__(self, ui, cpt, update=None, title=''):

        super(CptPropertiesDialog, self).__init__(ui, cpt.name, title)

        self.cpt = cpt
        self.gcpt = cpt.gcpt
        self.update = update

        entries = []
        if self.gcpt.kinds != {}:
            kind_name = self.gcpt.kinds[self.gcpt.kind]
            entries.append(LabelEntry(
                'kind', 'Kind', kind_name, list(self.gcpt.kinds.values()),
                command=self.on_update))

        if self.gcpt.styles != {}:
            style_name = self.gcpt.styles[self.gcpt.style]
            entries.append(LabelEntry(
                'style', 'Style', style_name, list(self.gcpt.styles.values()),
                command=self.on_update))

        entries.append(LabelEntry('name', 'Name', self.cpt.name,
                                  command=self.on_update))

        for m, arg in enumerate(self.gcpt.args):
            if arg == 'Control':
                continue
            entries.append(LabelEntry(arg, arg, self.cpt.args[m],
                                      command=self.on_update))

        if cpt.is_capacitor:
            v0 = str(self.cpt.cpt.v0) if self.cpt.cpt.has_ic else ''
            entries.append(LabelEntry('v0', 'v0', v0,
                                      command=self.on_update))
        elif cpt.is_inductor:
            i0 = str(self.cpt.cpt.i0) if self.cpt.cpt.has_ic else ''
            entries.append(LabelEntry('i0', 'i0', i0,
                                      command=self.on_update))
        elif cpt.is_dependent_source and self.gcpt.type != 'Eopamp':
            names = ui.model.possible_control_names()
            entries.append(LabelEntry('control', 'Control',
                                      self.gcpt.control, names,
                                      command=self.on_update))

        for k, v in self.gcpt.fields.items():
            entries.append(LabelEntry(k, v, getattr(self.gcpt, k),
                                      command=self.on_update))

        for k, v in self.gcpt.extra_fields.items():
            entries.append(LabelEntry(k, v, getattr(self.gcpt, k),
                                      command=self.on_update))

        self.labelentries = LabelEntries(self, ui, entries)

        button = Button(self, text="OK", command=self.on_ok)
        button.grid(row=self.labelentries.row)
        self.focus()

    def on_update(self, arg=None):

        if self.gcpt.kinds != {}:
            kind = self.gcpt.inv_kinds[self.labelentries.get('kind')]
            if self.gcpt.kind != kind:
                self.gcpt.kind = kind
                # Need a new cpt

        if self.gcpt.styles != {}:
            self.gcpt.style = self.gcpt.inv_styles[self.labelentries.get(
                'style')]

        name = self.labelentries.get('name')
        if name.startswith(self.gcpt.name[0]):
            self.gcpt.name = self.labelentries.get('name')
        else:
            self.ui.show_error_dialog('Cannot change component type')

        newargs = ()
        for m, arg in enumerate(self.gcpt.args):
            if arg == 'Control':
                newargs += (arg, )
                continue
            value = self.labelentries.get(arg)
            if value == '':
                value = self.gcpt.name
            newargs += (value, )

        self.cpt.args = newargs

        try:
            if self.cpt.is_capacitor:
                v0 = self.labelentries.get('v0')
                self.cpt.args[-1] = v0
                if v0 == '' or v0 is None:
                    v0 = None
                else:
                    try:
                        v0 = float(v0)
                    except (TypeError, ValueError):
                        # Symbolic
                        pass

                cpt = self.cpt.cpt
                # Create new oneport (this should be improved).
                self.cpt._cpt = cpt.__class__(cpt.C, v0)
            elif self.cpt.is_inductor:
                i0 = self.labelentries.get('i0')
                self.cpt.args[-1] = i0
                if i0 == '' or i0 is None:
                    i0 = None
                else:
                    try:
                        i0 = float(i0)
                    except (TypeError, ValueError):
                        # Symbolic
                        pass
                cpt = self.cpt.cpt
                # Create new oneport (this should be improved).
                self.cpt._cpt = cpt.__class__(cpt.L, i0)
        except KeyError:
            pass

        try:
            self.gcpt.control = self.labelentries.get('control')
        except KeyError:
            pass

        for k, v in self.gcpt.fields.items():
            setattr(self.gcpt, k, self.labelentries.get(k))

        for k, v in self.gcpt.extra_fields.items():
            setattr(self.gcpt, k, self.labelentries.get(k))

        if self.update:
            self.update(self.cpt)

    def on_ok(self):

        # In case user does not hit enter
        self.on_update()
        self.on_close()
