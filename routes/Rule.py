class Rule(object):
    def __init__(self, cfg, name, frontend_names, pool, fd_name, fd_group):
        if not cfg:
            raise ValueError('cfg cannot be None')
        self.action = None
        self.name = name
        self.ruletype = cfg['ruletype'] if 'ruletype' in cfg else 'Forward'

        if self.ruletype and not self.ruletype == 'None':
            if self.ruletype.lower() == 'forward':
                self.ruletype = 'Forward'
            else:
                self.ruletype = 'Redirect'

            self.redirect_type = cfg['redirect-type'] if 'redirect-type' in cfg else 'Found'
            self.redirect_protocol = cfg['redirect-protocol'] if 'redirect-protocol' in cfg else 'MatchRequest'
            self.dest_host = cfg['destination-host'] if 'destination-host' in cfg else None
            self.dest_path = cfg['destination-path'] if 'destination-path' in cfg else None
            self.patterns = cfg['patterns'] if 'patterns' in cfg else ['/*']
            self.forward_protocol = cfg['forward-protocol'] if 'forward-protocol' in cfg else 'MatchRequest'
            self.forward_path = cfg['forward-path'] if 'forward-path' in cfg else None
            self.protocols = cfg['protocols'] if 'protocols' in cfg else ['Https', 'Http']
            self.disable_rule = cfg['disable'] if 'disable' in cfg else False

            self.action = 'create'
            self.command = ['az', 'network', 'front-door']
            self.command.extend(['routing-rule', self.action])
            self.command.extend(['--route-type', self.ruletype])
            self.command.extend(['--front-door-name', fd_name])
            self.command.extend(['--resource-group', fd_group])
            self.command.extend(['--name', self.name])
            self.command.extend(['--disabled', str(self.disable_rule).lower()])
            self.command.extend(['--frontend-endpoints'])
            for fe in frontend_names:
                self.command.extend([fe])
            self.command.extend(['--patterns'])
            for p in self.patterns:
                self.command.extend([p])
            self.command.extend(['--accepted-protocols'])
            for p in self.protocols:
                self.command.extend([p])

            if self.ruletype == 'Forward':
                if not pool:
                    raise TypeError('backend pool cannot be null when ruletype is Forward')
                self.command.extend(['--backend-pool', pool])
                self.command.extend(['--forwarding-protocol', self.forward_protocol])
                if self.forward_path:
                    self.command.extend(['--custom-forwarding-path', self.forward_path])

            if self.ruletype == 'Redirect':
                self.command.extend(['--redirect-type', self.redirect_type])
                self.command.extend(['--redirect-protocol', self.redirect_protocol])
                if self.dest_host:
                    self.command.extend(['--custom-host', self.dest_host])
                if self.dest_path:
                    self.command.extend(['--custom-path', self.dest_path])

