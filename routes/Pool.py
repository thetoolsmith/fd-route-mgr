import json
from routes import Probe
from routes import LoadBalancing
from routes import Utility as util

class Pool(object):
    def __init__(self, cfg, fd_name, fd_group):
        if not cfg:
            raise ValueError('cfg cannot be None')

        self.name = None
        _config = json.loads(json.dumps(cfg))
        for k,v in _config.items():
            if not self.name: self.name = k
        self.create_pool = not _config[self.name]['exists'] if 'exists' in _config[self.name] else False

        self.pool_cfg = _config[self.name]

        if self.create_pool:
            self.backends = self.pool_cfg['backends'] if 'backends' in self.pool_cfg else None # list of dict [{}]
            if not self.backends:
                raise TypeError('missing backends config')
            self.num_backends = len(self.backends)
            self.disable_probe = False
            self.disable_pool = self.pool_cfg['disable'] if 'disable' in self.pool_cfg else False
            self.http_port = self.pool_cfg['http-port'] if 'http-port' in self.pool_cfg else 80
            self.https_port = self.pool_cfg['https-port'] if 'https-port' in self.pool_cfg else 443
            self.priority = self.pool_cfg['priority'] if 'priority' in self.pool_cfg else 1
            self.weight = self.pool_cfg['weight'] if 'weight' in self.pool_cfg else 50
            self.probe = None
            if 'probe' in self.pool_cfg and self.pool_cfg['probe']:
                self.probe = Probe.Probe(self.pool_cfg['probe'], self.name, fd_name, fd_group)

            self.loadbalancing = None
            if 'load-balancing' in self.pool_cfg and self.pool_cfg['load-balancing']:
                self.loadbalancing = LoadBalancing.LoadBalancing(self.pool_cfg['load-balancing'], self.name, fd_name, fd_group)

            self.action = 'show'
            self.command = ['az', 'network', 'front-door']
            self.command.extend(['backend-pool', self.action])
            self.command.extend(['--front-door-name', fd_name])
            self.command.extend(['--resource-group', fd_group])
            self.command.extend(['--name', self.name])

            success, result = util.execute(self.command)

            if not success or 'Not Found' in result:
                self.action = 'create'
                self.command = ['az', 'network', 'front-door']
                self.command.extend(['backend-pool', self.action])
                self.command.extend(['--front-door-name', fd_name])
                self.command.extend(['--resource-group', fd_group])
                self.command.extend(['--name', self.name])
                self.command.extend(['--probe', self.probe.name])
                self.command.extend(['--load-balancing', self.loadbalancing.name])

                self.command.extend(['--address', next(iter(self.backends[0]))]) #if len(self.backends) > 1, need to update backend after creating it
                if 'host-header' in self.backends[0] and self.backends[0]["host-header"]:
                    self.command.extend(['--backend-host-header', self.backends[0]["host-header"]])

                self.command.extend(['--http-port', str(self.http_port)])
                self.command.extend(['--https-port', str(self.https_port)])
                self.command.extend(['--priority', str(self.priority)])
                self.command.extend(['--weight', str(self.weight)])
                self.command.extend(['--disabled', 'false'])
