from routes import Utility as util

class LoadBalancing(object):
    def __init__(self, cfg, poolname, fd_name, fd_group):
        if not cfg:
            raise ValueError('cfg cannot be None')
        self.action = None
        self.name = f'lb-{poolname}'
        self.sample_size = 4
        self.samples = 2
        self.latency = 0
        if 'name' in cfg:
            self.name = cfg['name'] #must exist
            self.command = []
        else:
            self.sample_size = cfg['sample-size'] if 'sample-size' in cfg else self.sample_size
            self.samples = cfg['samples'] if 'samples' in cfg else self.samples
            self.latency = cfg['latency'] if 'latency' in cfg else self.latency
            self.action = 'show'

            _cmd = ['az', 'network', 'front-door']
            _cmd.extend(['load-balancing', self.action])
            _cmd.extend(['--front-door-name', fd_name])
            _cmd.extend(['--resource-group', fd_group])
            _cmd.extend(['--name', self.name])

            success, result = util.execute(_cmd)
            if result and 'does not exist' in result:
                self.action = 'create'
            else:
                print(f'loadbalancing {self.name} exists')
                self.action = None

            self.command = ['az', 'network', 'front-door']
            self.command.extend(['load-balancing', self.action])
            self.command.extend(['--front-door-name', fd_name])
            self.command.extend(['--resource-group', fd_group])
            self.command.extend(['--name', self.name])
            self.command.extend(['--sample-size', str(self.sample_size)])
            self.command.extend(['--successful-samples-required', str(self.samples)])
            self.command.extend(['--additional-latency', str(self.latency)])

