from routes import Utility as util

class Probe(object):

    def __init__(self, cfg, poolname, fd_name, fd_group):
        if not cfg:
            raise ValueError('cfg cannot be None')
        self.action = None
        self.disable = cfg['disable'] if 'disable' in cfg else False
        self.name = f'probe-{poolname}'
        self.interval = 120
        self.protocol = 'Https'
        self.path = '/'
        if 'name' in cfg:
            self.name = cfg['name'] #must exist
            self.command = []
        else:
            self.action = 'show'
            self.interval = cfg['interval'] if 'interval' in cfg else self.interval
            self.protocol = cfg['protocol'] if 'protocol' in cfg else self.protocol
            self.path = cfg['path'] if 'path' in cfg else self.path
            _cmd = ['az', 'network', 'front-door']
            _cmd.extend(['probe', self.action])
            _cmd.extend(['--front-door-name', fd_name])
            _cmd.extend(['--resource-group', fd_group])
            _cmd.extend(['--name', self.name])

            success, result = util.execute(_cmd)
            if result and 'does not exist' in result:
                self.action = 'create'
            else:
                print(f'probe {self.name} exists')
                self.action = 'update'

            self.command = ['az', 'network', 'front-door']
            self.command.extend(['probe', self.action])
            self.command.extend(['--front-door-name', fd_name])
            self.command.extend(['--resource-group', fd_group])
            self.command.extend(['--name', self.name])
            self.command.extend(['--protocol', self.protocol])
            if self.disable:
                self.command.extend(['--enabled', 'Disabled'])
            self.command.extend(['--interval', str(self.interval)])
            self.command.extend(['--path', self.path])
            self.command.extend(['--probeMethod', "GET"])

