class Components(list):

    def __init__(self):

        super(Components, self).__init__(self)
        self.kinds = {}

    def add(self, cpt, name, *nodes):

        if cpt.TYPE not in self.kinds:
            self.kinds[cpt.TYPE] = []
        self.kinds[cpt.TYPE].append(name)

        cpt.name = name
        cpt.value = name
        cpt.nodes = nodes

        self.append(cpt)

    def add_auto(self, cpt, *nodes):
        """Enumerate component before adding."""

        if cpt.TYPE not in self.kinds:
            name = cpt.TYPE + '1'
        else:
            num = 1
            while True:
                name = cpt.TYPE + str(num)
                if name not in self.kinds[cpt.TYPE]:
                    break
                num += 1

        self.add(cpt, name, *nodes)

    def clear(self):

        while self != []:
            # TODO erase component?
            self.pop()

    def debug(self):

        s = ''
        for cpt in self:
            s += cpt.name + ' ' + \
                ' '.join([str(node) for node in cpt.nodes]) + '\n'
        return s + '\n'

    def as_sch(self, step):

        nets = []
        for cpt in self:
            nets.append(cpt.net(self, step=step))
        return '\n'.join(nets) + '\n'

    def closest(self, x, y):

        for cpt in self:

            lsq = cpt.length() ** 2
            xm, ym = cpt.midpoint
            rsq = (xm - x)**2 + (ym - y)**2
            if rsq < 0.1 * lsq:
                return cpt
        return None

    def find_index(self, name):

        for m, cpt in enumerate(self):
            if cpt.name == name:
                return m
        raise ValueError('Unknown component ' + name)

    def remove(self, cpt):

        idx = self.index(cpt)
        if idx is None:
            raise ValueError('Unknown component ' + cpt.name)

        cpt = self.pop(idx)

        return cpt
